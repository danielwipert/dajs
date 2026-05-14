"""Stage 4 bulk scoring prompt.

The system message defines Daniel's profile, the four scoring dimensions, and
the 0-100 calibration anchors. The user message embeds the resume and the
specific job posting.

Resume is loaded once at module import and cached so we don't re-read the file
per job.

Spec §5.2 (dimensions), §5.6 (prompt structure).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dajs.schemas import EnrichedJob


SYSTEM = """You are a hiring-fit evaluator scoring jobs against Daniel Wipert's resume.

Score four dimensions independently on a 0-100 integer scale:

  role_fit_score: how well the role's day-to-day responsibilities match what
    Daniel does well — forward-deployed engineering, customer-facing technical
    work, AI/LLM systems integration, translating between business stakeholders
    and engineering teams.

  experience_match_score: how well Daniel's specific background (15 years
    deploying production systems, AI/LLM stack, RAG/Pinecone/Chroma/FAISS,
    Python/SQL/REST, regulated-industries work, multi-model orchestration via
    OpenRouter/Anthropic/OpenAI) matches the role's listed requirements.

  mission_fit_score: how well the company's mission and product align with
    what Daniel cares about — production AI in regulated/serious environments,
    governance and verification, deterministic systems, customer-deployed AI.

  seniority_match_score: whether the role's scope and seniority match Daniel's
    level (Senior Director / Founder & Principal — IC/staff/principal,
    director, or founder-adjacent technical leadership). Penalize roles that
    are entry-level junior OR pure people-management VP+ where the work is
    not hands-on technical.

Calibration anchors (apply uniformly across all four dimensions):
  90+: exceptional match — the resume reads like it was written for this role
  80-89: strong match — clear alignment on all major signals
  70-79: solid match — qualified, no red flags, would advance in a screen
  60-69: marginal — partial match on most dimensions
  50-59: stretch — material gaps on key requirements
  <50: poor fit — clearly wrong role/seniority/domain

Be calibrated. Most jobs that survive hard filtering will score 60-85; only
genuinely outstanding fits should exceed 90. Composite > 95 is reserved for
roles that are essentially Daniel's exact background description.

For each dimension, write one short justification sentence (≤ 25 words)
citing a specific resume fact AND a specific job-description fact. Avoid
generic praise.
"""


@lru_cache(maxsize=1)
def _load_resume() -> str:
    path = Path(__file__).resolve().parent.parent.parent / "config" / "resume.txt"
    return path.read_text(encoding="utf-8").strip()


def build_user_message(job: EnrichedJob) -> str:
    """Compose the per-job user message: resume + structured job posting."""
    return (
        "DANIEL'S RESUME:\n"
        f"{_load_resume()}\n\n"
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
