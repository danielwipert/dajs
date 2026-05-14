"""Stage 4 — Bulk scoring.

For each EnrichedJob: send the resume + job posting to the bulk LLM, parse the
four-dimension score, compute composite (simple average), and build a ScoredJob.

Single retry on parse/validation failure is handled inside OpenRouterProvider.
A second-failure here is logged and the job is dropped from this run (NOT
added to dedup, so it gets retried tomorrow).

Spec §5.1, §5.2, §5.3.
"""

from __future__ import annotations

import logging

from dajs.prompts.bulk_score import SYSTEM, build_user_message
from dajs.providers.llm_base import LLMProvider
from dajs.schemas import BulkScoringOutput, EnrichedJob, ScoredJob

log = logging.getLogger(__name__)


def _composite(scores: BulkScoringOutput) -> float:
    return (
        scores.role_fit_score
        + scores.experience_match_score
        + scores.mission_fit_score
        + scores.seniority_match_score
    ) / 4.0


def run_bulk_score(
    jobs: list[EnrichedJob],
    llm: LLMProvider,
    config: dict,
) -> list[ScoredJob]:
    model = config["bulk_model"]
    out: list[ScoredJob] = []

    for job in jobs:
        try:
            scoring = llm.complete(SYSTEM, build_user_message(job), model, BulkScoringOutput)
        except Exception as e:  # noqa: BLE001
            log.warning(
                "bulk-score failed for %s @ %s (%s): %s",
                job.title, job.company, model, e,
            )
            continue

        out.append(
            ScoredJob(
                **job.model_dump(),
                role_fit_score=scoring.role_fit_score,
                experience_match_score=scoring.experience_match_score,
                mission_fit_score=scoring.mission_fit_score,
                seniority_match_score=scoring.seniority_match_score,
                composite_score=_composite(scoring),
                dimension_justifications=scoring.justifications,
            )
        )

    log.info("Stage 4 bulk-score: %d in → %d scored (model=%s)", len(jobs), len(out), model)
    return out


def filter_and_rank(
    scored: list[ScoredJob],
    config: dict,
) -> list[ScoredJob]:
    """Drop below-threshold, sort by composite desc, take top review_top_n.
    Spec §5.3 + Step 4.6."""
    threshold = config["score_threshold"]
    top_n = config["review_top_n"]

    survivors = [s for s in scored if s.composite_score >= threshold]
    survivors.sort(key=lambda s: s.composite_score, reverse=True)
    survivors = survivors[:top_n]
    log.info(
        "Stage 4 threshold (>=%.0f): %d survived; top-%d advanced",
        threshold, len([s for s in scored if s.composite_score >= threshold]), len(survivors),
    )
    return survivors
