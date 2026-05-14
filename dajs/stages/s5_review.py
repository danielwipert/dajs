"""Stage 5 — Final review.

Top-N scorers from Stage 4 are sent to the top-tier review model. The reviewer
returns adjusted dimension scores + a rationale. We build a PublishedJob from
each successful review.

Failures here drop the job from this run (NOT added to dedup) — same pattern
as Stage 4.

Spec §5.1 (verifier role), §5.6 (prompt), Step 4.8.
"""

from __future__ import annotations

import logging
from datetime import date

from dajs.prompts.final_review import SYSTEM, build_user_message
from dajs.providers.llm_base import LLMProvider
from dajs.schemas import FinalReviewOutput, PublishedJob, ScoredJob

log = logging.getLogger(__name__)


def run_final_review(
    jobs: list[ScoredJob],
    llm: LLMProvider,
    config: dict,
    today: str | None = None,
) -> list[PublishedJob]:
    model = config["review_model"]
    today_iso = today or date.today().isoformat()
    out: list[PublishedJob] = []

    for job in jobs:
        try:
            review = llm.complete(SYSTEM, build_user_message(job), model, FinalReviewOutput)
        except Exception as e:  # noqa: BLE001
            log.warning(
                "final-review failed for %s @ %s (%s): %s",
                job.title, job.company, model, e,
            )
            continue

        # Carry forward the bulk-stage fields, then overwrite with reviewer's
        # adjusted scores. ScoredJob fields stay at their bulk values for audit;
        # PublishedJob exposes the reviewer's final_composite_score and rationale.
        out.append(
            PublishedJob(
                **job.model_dump(),
                final_composite_score=review.final_composite_score,
                rationale=review.rationale,
                published_date=today_iso,
            )
        )

    log.info("Stage 5 review: %d in → %d reviewed (model=%s)", len(jobs), len(out), model)
    return out


def take_top_for_publication(jobs: list[PublishedJob], config: dict) -> list[PublishedJob]:
    """After review, sort by final_composite_score desc and cap at max_jobs_per_day.
    Spec §5.3 / Step 4.9."""
    cap = config["max_jobs_per_day"]
    ordered = sorted(jobs, key=lambda j: j.final_composite_score, reverse=True)[:cap]
    log.info("Stage 5 publication cap (max=%d): %d → %d", cap, len(jobs), len(ordered))
    return ordered
