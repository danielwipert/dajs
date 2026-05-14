"""Stub LLM provider — returns deterministic scoring output for offline development.

Generates scores by hashing the user prompt so the same input → same output
across runs, but different jobs get different scores.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel

from dajs.schemas import BulkScoringOutput, FinalReviewOutput


def _seed_int(text: str, low: int, high: int, salt: str = "") -> int:
    h = hashlib.sha256((salt + text).encode("utf-8")).digest()
    span = high - low + 1
    return low + (int.from_bytes(h[:4], "big") % span)


class StubLLMProvider:
    """Returns canned structured output for the two scoring schemas."""

    def complete(
        self,
        system: str,
        user: str,
        model: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        if schema is BulkScoringOutput:
            return BulkScoringOutput(
                role_fit_score=_seed_int(user, 50, 95, "role"),
                experience_match_score=_seed_int(user, 50, 95, "exp"),
                mission_fit_score=_seed_int(user, 50, 95, "mission"),
                seniority_match_score=_seed_int(user, 50, 95, "seniority"),
                justifications={
                    "role_fit": "Stub: role looks like a deployment-engineering fit.",
                    "experience_match": "Stub: years and stack appear aligned.",
                    "mission_fit": "Stub: company mission seems compatible.",
                    "seniority_match": "Stub: seniority level appears right.",
                },
            )

        if schema is FinalReviewOutput:
            return FinalReviewOutput(
                role_fit_score=_seed_int(user, 60, 95, "r-role"),
                experience_match_score=_seed_int(user, 60, 95, "r-exp"),
                mission_fit_score=_seed_int(user, 60, 95, "r-mission"),
                seniority_match_score=_seed_int(user, 60, 95, "r-seniority"),
                final_composite_score=float(_seed_int(user, 70, 95, "r-comp")),
                rationale=(
                    "Stub rationale: strong forward-deployed flavor, customer-facing "
                    "engineering, and senior-leaning scope match Daniel's trajectory."
                ),
            )

        raise ValueError(f"StubLLMProvider doesn't know schema {schema!r}")
