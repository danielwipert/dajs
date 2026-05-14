"""Stage 5 final-review prompt.

The top scorers from Stage 4 are sent to the top-tier review model with their
bulk scores attached. The reviewer is asked to (a) confirm or revise each
dimension score, (b) write a short 'why this fits Daniel' rationale.

Reuses the same SYSTEM as bulk scoring for consistency in the calibration
anchors, with an additional instruction block tailored to review.

Spec §5.6.
"""

from __future__ import annotations

from dajs.prompts.bulk_score import SYSTEM as BULK_SYSTEM
from dajs.prompts.bulk_score import _load_resume
from dajs.schemas import ScoredJob


SYSTEM = (
    BULK_SYSTEM
    + "\n\n"
    "ADDITIONAL REVIEW INSTRUCTIONS:\n"
    "You are reviewing a job that survived an initial bulk scoring pass with a "
    "cheaper model. The bulk model's scores are attached for your reference; "
    "you may confirm them, raise them, or lower them based on your own reading. "
    "Write a final_composite_score that is the simple average of your four "
    "(possibly-revised) dimension scores.\n\n"
    "Also write a `rationale` field (1-2 sentences, ≤ 50 words) that explains "
    "why this is a good fit for Daniel specifically — citing the most concrete "
    "intersection between the job description and his resume. This rationale "
    "is what Daniel will read on the daily site, so make it informative, "
    "calibrated, and specific. No marketing language."
)


def build_user_message(job: ScoredJob) -> str:
    return (
        "DANIEL'S RESUME:\n"
        f"{_load_resume()}\n\n"
        "BULK SCORING RESULT (FYI — feel free to adjust):\n"
        f"  role_fit_score:        {job.role_fit_score}\n"
        f"  experience_match_score: {job.experience_match_score}\n"
        f"  mission_fit_score:      {job.mission_fit_score}\n"
        f"  seniority_match_score:  {job.seniority_match_score}\n"
        f"  composite (avg):        {job.composite_score:.1f}\n"
        "  dimension justifications:\n"
        + "".join(f"    {k}: {v}\n" for k, v in job.dimension_justifications.items())
        + "\n"
        "JOB POSTING:\n"
        f"Title: {job.title}\n"
        f"Company: {job.company}\n"
        f"Location: {job.location}\n"
        f"ATS: {job.ats_platform.value}\n"
        f"Employment type: {job.employment_type or 'unspecified'}\n"
        f"Apply URL: {job.apply_url}\n\n"
        "Description:\n"
        f"{job.description}"
    )
