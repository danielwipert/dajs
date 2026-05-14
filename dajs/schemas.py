"""Pydantic data models for every payload that flows through the DAJS pipeline.

Each model in the RawJob → PublishedJob chain inherits from the previous one
so the pipeline can only ever add fields, never lose them.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class ATSPlatform(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    DOVER = "dover"
    BAMBOOHR = "bamboohr"
    RECRUITEE = "recruitee"
    SMARTRECRUITERS = "smartrecruiters"


class LocationCategory(str, Enum):
    CHICAGO = "chicago"
    AUSTIN = "austin"
    REMOTE = "remote"


class RawJob(BaseModel):
    """Direct output of the search provider.

    `company` and `location` are best-effort at this stage: Google Web Search
    snippets often omit them. Phase 3 (enrichment) re-extracts both from the
    actual ATS page and overwrites these fields on the EnrichedJob.
    """

    title: str
    company: str = ""
    location: str = ""
    apply_url: HttpUrl
    posted_date: str | None = None
    snippet: str | None = None


class FilteredJob(RawJob):
    """RawJob that passed ATS allowlist, location, and dedup filters.

    `location_category` may be None at this stage if the search snippet didn't
    yield enough signal. Phase 3 re-extracts location from the ATS page and
    sets a definitive category (or drops the job).
    """

    job_id: str
    ats_platform: ATSPlatform
    location_category: LocationCategory | None = None


class EnrichedJob(FilteredJob):
    """FilteredJob plus the full job description fetched from the ATS page."""

    description: str
    department: str | None = None
    employment_type: str | None = None
    compensation: str | None = None


class ScoredJob(EnrichedJob):
    """EnrichedJob plus Stage 4 bulk scoring output."""

    role_fit_score: int = Field(ge=0, le=100)
    experience_match_score: int = Field(ge=0, le=100)
    mission_fit_score: int = Field(ge=0, le=100)
    seniority_match_score: int = Field(ge=0, le=100)
    composite_score: float
    dimension_justifications: dict[str, str]


class PublishedJob(ScoredJob):
    """ScoredJob that survived Stage 5 final review — the final published form."""

    final_composite_score: float
    rationale: str
    published_date: str


class BulkScoringOutput(BaseModel):
    """LLM response schema for Stage 4 bulk scoring."""

    role_fit_score: int = Field(ge=0, le=100)
    experience_match_score: int = Field(ge=0, le=100)
    mission_fit_score: int = Field(ge=0, le=100)
    seniority_match_score: int = Field(ge=0, le=100)
    justifications: dict[str, str]


class FinalReviewOutput(BaseModel):
    """LLM response schema for Stage 5 final review."""

    role_fit_score: int = Field(ge=0, le=100)
    experience_match_score: int = Field(ge=0, le=100)
    mission_fit_score: int = Field(ge=0, le=100)
    seniority_match_score: int = Field(ge=0, le=100)
    final_composite_score: float
    rationale: str
