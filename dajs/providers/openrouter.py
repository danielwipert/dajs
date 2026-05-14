"""OpenRouter implementation of the LLMProvider Protocol.

Uses the OpenAI-compatible /chat/completions endpoint with
`response_format={"type": "json_object"}` and the requested schema embedded
in the system prompt. Re-parses with the caller-supplied Pydantic model
and retries once on JSON or validation errors.

Usage accounting: every successful call increments self.usage so the
orchestrator can report total tokens + cost in run_log.json.

Spec §5.4, §8.3, §9.2.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, TypeVar

import requests
from pydantic import BaseModel, ValidationError


ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_TIMEOUT_S = 60
MAX_RETRIES = 2  # one initial attempt + one retry on parse/validation failure
RETRY_BACKOFF_S = 2.0

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class OpenRouterError(RuntimeError):
    """Raised when OpenRouter returns an unrecoverable error."""


@dataclass
class Usage:
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    by_model: dict[str, dict[str, float | int]] = field(default_factory=dict)

    def add(self, model: str, usage: dict[str, Any], cost: float | None) -> None:
        self.calls += 1
        pt = int(usage.get("prompt_tokens", 0) or 0)
        ct = int(usage.get("completion_tokens", 0) or 0)
        tt = int(usage.get("total_tokens", pt + ct) or pt + ct)
        self.prompt_tokens += pt
        self.completion_tokens += ct
        self.total_tokens += tt
        if cost is not None:
            self.cost_usd += float(cost)
        bucket = self.by_model.setdefault(
            model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
        )
        bucket["calls"] = int(bucket["calls"]) + 1
        bucket["prompt_tokens"] = int(bucket["prompt_tokens"]) + pt
        bucket["completion_tokens"] = int(bucket["completion_tokens"]) + ct
        if cost is not None:
            bucket["cost_usd"] = float(bucket["cost_usd"]) + float(cost)


def _augment_system_with_schema(system: str, schema_cls: type[BaseModel]) -> str:
    """Append the requested JSON schema to the system message so the model
    knows the exact shape to produce."""
    schema = schema_cls.model_json_schema()
    return (
        f"{system}\n\n"
        "Respond ONLY with a single JSON object matching this schema, no prose:\n"
        f"{json.dumps(schema, indent=2)}"
    )


def _extract_message_content(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise OpenRouterError(f"OpenRouter response had no choices: {payload}")
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if not isinstance(content, str) or not content.strip():
        raise OpenRouterError(f"OpenRouter response had no text content: {choices[0]}")
    return content


def _parse_json_loose(text: str) -> Any:
    """Parse model output as JSON, tolerating ```json fences."""
    s = text.strip()
    if s.startswith("```"):
        # Strip the first ``` (optionally followed by 'json') and the trailing ```
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl + 1 :]
        if s.endswith("```"):
            s = s[: -3]
        s = s.strip()
    return json.loads(s)


class OpenRouterProvider:
    """LLMProvider implementation for OpenRouter's /chat/completions endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int = DEFAULT_TIMEOUT_S,
        referer: str | None = None,
        app_name: str = "DAJS",
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise OpenRouterError(
                "OPENROUTER_API_KEY not set. Add it to .env or export it before running."
            )
        self.timeout = timeout
        self.usage = Usage()
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": referer or "https://github.com/danielwipert/dajs",
            "X-Title": app_name,
        }

    def complete(
        self,
        system: str,
        user: str,
        model: str,
        schema: type[T],
    ) -> T:
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": _augment_system_with_schema(system, schema)},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "usage": {"include": True},  # request cost field if available
        }

        last_err: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    ENDPOINT, headers=self._headers, json=body, timeout=self.timeout
                )
            except requests.RequestException as e:
                last_err = e
                log.warning("OpenRouter transport error (attempt %d): %s", attempt, e)
                time.sleep(RETRY_BACKOFF_S * attempt)
                continue

            if resp.status_code in (429, 502, 503, 504):
                log.warning(
                    "OpenRouter HTTP %d (attempt %d): %s",
                    resp.status_code, attempt, resp.text[:200],
                )
                time.sleep(RETRY_BACKOFF_S * attempt)
                continue
            if resp.status_code == 401:
                raise OpenRouterError("OpenRouter auth failed (401). Check OPENROUTER_API_KEY.")
            if not resp.ok:
                raise OpenRouterError(
                    f"OpenRouter HTTP {resp.status_code}: {resp.text[:400]}"
                )

            try:
                payload = resp.json()
            except ValueError as e:
                last_err = e
                log.warning("OpenRouter returned non-JSON (attempt %d): %s", attempt, e)
                continue

            if payload.get("error"):
                err = payload["error"]
                # Some errors are transient (rate-limit relayed inside body)
                if isinstance(err, dict) and err.get("code") in (429, 502, 503, 504):
                    log.warning("OpenRouter inline error (attempt %d): %s", attempt, err)
                    time.sleep(RETRY_BACKOFF_S * attempt)
                    continue
                raise OpenRouterError(f"OpenRouter error: {err}")

            try:
                content = _extract_message_content(payload)
                obj = _parse_json_loose(content)
                result = schema.model_validate(obj)
            except (json.JSONDecodeError, ValidationError, OpenRouterError) as e:
                last_err = e
                log.warning("OpenRouter parse/validate error (attempt %d): %s", attempt, e)
                continue

            self._record_usage(model, payload)
            return result

        raise OpenRouterError(
            f"OpenRouter failed after {MAX_RETRIES} attempts: {last_err}"
        )

    def _record_usage(self, model: str, payload: dict) -> None:
        usage = payload.get("usage") or {}
        cost = usage.get("cost")
        self.usage.add(model, usage, cost)
