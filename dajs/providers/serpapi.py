"""SerpAPI implementation of the SearchProvider Protocol.

Uses Google Web Search (engine=google) with a `site:` filter constructed from
the configured ATS allowlist. This guarantees every result lands on an approved
one-page-apply ATS, sidestepping Google Jobs' aggregator bias toward
LinkedIn/Indeed/proprietary career sites.

Result parsing:
  Each `organic_results[i]` has `title`, `link`, `snippet`, optional `displayed_link`.
  We populate RawJob.apply_url from `link` and RawJob.snippet from `snippet`.
  RawJob.title is the search-result title (typically "Role - Company - Greenhouse").
  Company and location are best-effort: snippet text is the only signal at this
  stage. Phase 3 (enrichment) re-extracts these from the actual ATS page.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any
from urllib.parse import urlparse

import requests
from pydantic import ValidationError

from dajs.schemas import RawJob


SERPAPI_URL = "https://serpapi.com/search"
DEFAULT_TIMEOUT_S = 30
MAX_RETRIES = 2
RETRY_BACKOFF_S = 2.0

log = logging.getLogger(__name__)


class SerpAPIError(RuntimeError):
    """Raised when SerpAPI returns an unrecoverable error."""


_LOCATION_HINT_RE = re.compile(
    r"\b(Chicago(?:,?\s*IL(?:linois)?)?|Austin(?:,?\s*TX(?:exas)?)?|Remote(?:\s*-?\s*US)?)\b",
    re.IGNORECASE,
)


def _split_title_company(title: str) -> tuple[str, str]:
    """Best-effort split of a Google search-result title.

    Patterns we commonly see:
      "Forward Deployed Engineer at Acme | Greenhouse"
      "Forward Deployed Engineer - Acme - Lever"
      "Acme - Senior FDE - Ashby"

    Returns (role_title, company_guess). Phase 3 backstops both.
    """
    # Strip platform suffixes
    cleaned = re.sub(
        r"\s*[|\-–—]\s*(Greenhouse|Lever|Ashby|Dover|BambooHR|Recruitee|SmartRecruiters).*$",
        "",
        title,
        flags=re.IGNORECASE,
    ).strip()

    m = re.match(r"^(?P<role>.+?)\s+(?:at|@)\s+(?P<company>.+)$", cleaned, re.IGNORECASE)
    if m:
        return m.group("role").strip(), m.group("company").strip()

    # Fallback: split on the last " - "
    if " - " in cleaned:
        head, _, tail = cleaned.rpartition(" - ")
        if head and tail:
            return head.strip(), tail.strip()

    return cleaned, ""


def _company_from_url(url: str) -> str:
    """Best-effort company extraction from an ATS URL path.

    Most ATS URLs encode the org slug as the first path segment:
      boards.greenhouse.io/acmeai/jobs/123 → "acmeai"
      jobs.lever.co/brightside/abc → "brightside"
      jobs.ashbyhq.com/cobalt/eng-impl → "cobalt"
      foo.recruitee.com/o/role → "foo"  (subdomain wins for Recruitee/BambooHR)
    """
    parsed = urlparse(url)
    host = parsed.hostname or ""
    path_parts = [p for p in (parsed.path or "").split("/") if p]

    # Subdomain-as-tenant ATS platforms.
    for tenant_host in (".recruitee.com", ".bamboohr.com"):
        if host.endswith(tenant_host):
            return host.split(".")[0]

    return path_parts[0] if path_parts else ""


def _location_from_snippet(snippet: str | None) -> str:
    if not snippet:
        return ""
    m = _LOCATION_HINT_RE.search(snippet)
    return m.group(1) if m else ""


def build_query(keywords: list[str], site_hosts: list[str] | None = None) -> str:
    """OR-joined keyword query, optionally restricted to specific hosts.

    Returns e.g.:
      ("forward deployed engineer" OR "AI engineer") (site:a.com OR site:b.com)
    """
    keyword_clause = "(" + " OR ".join(f'"{k}"' for k in keywords) + ")"
    if not site_hosts:
        return keyword_clause
    site_clause = "(" + " OR ".join(f"site:{h}" for h in site_hosts) + ")"
    return f"{keyword_clause} {site_clause}"


def site_hosts_from_ats_allowlist(ats_allowlist: dict[str, list[str]]) -> list[str]:
    """Derive Google `site:` host strings from the configured ATS URL patterns.

    Strips leading dots and any trailing path. Deduplicates while preserving
    insertion order so the generated query is stable across runs.
    """
    seen: dict[str, None] = {}
    for patterns in ats_allowlist.values():
        for pat in patterns:
            host = pat.lstrip(".").split("/", 1)[0]
            if host and host not in seen:
                seen[host] = None
    return list(seen.keys())


class SerpAPIProvider:
    """SearchProvider implementation backed by SerpAPI's Google Search endpoint."""

    def __init__(
        self,
        api_key: str | None = None,
        site_hosts: list[str] | None = None,
        timeout: int = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.api_key = api_key or os.environ.get("SERPAPI_KEY")
        if not self.api_key:
            raise SerpAPIError(
                "SERPAPI_KEY not set. Add it to .env or export it before running."
            )
        self.site_hosts = site_hosts or []
        self.timeout = timeout

    def search(self, query: str, params: dict) -> list[RawJob]:
        request_params: dict[str, Any] = {
            "engine": "google",
            "q": query,
            "api_key": self.api_key,
            **{k: v for k, v in params.items() if k != "engine"},
        }

        payload = self._request_with_retry(request_params)
        results = payload.get("organic_results") or []

        jobs: list[RawJob] = []
        for r in results:
            link = r.get("link")
            if not link:
                continue

            title_raw = r.get("title") or ""
            snippet = r.get("snippet")
            role_title, company_from_title = _split_title_company(title_raw)
            company = company_from_title or _company_from_url(link)
            location = _location_from_snippet(snippet)

            try:
                jobs.append(
                    RawJob(
                        title=role_title or title_raw,
                        company=company,
                        location=location,
                        apply_url=link,
                        posted_date=None,
                        snippet=snippet,
                    )
                )
            except ValidationError as e:
                log.warning("Skipping malformed result %r: %s", title_raw, e)

        log.info("SerpAPI returned %d organic results (parsed %d)", len(results), len(jobs))
        return jobs

    def _request_with_retry(self, params: dict[str, Any]) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.get(SERPAPI_URL, params=params, timeout=self.timeout)
            except requests.RequestException as e:
                last_exc = e
                log.warning("SerpAPI transport error (attempt %d): %s", attempt, e)
                time.sleep(RETRY_BACKOFF_S * attempt)
                continue

            if resp.status_code == 401:
                raise SerpAPIError("SerpAPI auth failed (401). Check SERPAPI_KEY.")
            if resp.status_code == 429:
                log.warning("SerpAPI rate-limited (429), attempt %d", attempt)
                time.sleep(RETRY_BACKOFF_S * attempt)
                continue
            if resp.status_code >= 500:
                log.warning("SerpAPI 5xx (%d), attempt %d", resp.status_code, attempt)
                time.sleep(RETRY_BACKOFF_S * attempt)
                continue
            if not resp.ok:
                raise SerpAPIError(
                    f"SerpAPI HTTP {resp.status_code}: {resp.text[:200]}"
                )

            try:
                data = resp.json()
            except ValueError as e:
                raise SerpAPIError(f"SerpAPI returned non-JSON: {e}") from e

            if data.get("error"):
                raise SerpAPIError(f"SerpAPI error: {data['error']}")
            return data

        raise SerpAPIError(
            f"SerpAPI failed after {MAX_RETRIES} attempts: {last_exc}"
        )
