"""Per-ATS extractor interface.

Each platform extractor exports an `extract(html, url) -> ExtractedJob` function.
`html` is the raw response body from a GET to the apply URL; `url` is the
canonical apply URL (some extractors need it for company-slug recovery).

ExtractedJob is intentionally a plain TypedDict (not Pydantic) — extractors
return best-effort partial data, and the caller composes them into the
EnrichedJob Pydantic model after applying defaults from the FilteredJob.
"""

from __future__ import annotations

from typing import TypedDict


class ExtractedJob(TypedDict, total=False):
    title: str
    company: str
    location: str
    description: str
    department: str | None
    employment_type: str | None
    compensation: str | None
    posted_date: str | None
