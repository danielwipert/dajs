"""Ashby job-page extractor.

Ashby's public job pages at jobs.ashbyhq.com/<org>/<job-id> are SPA-rendered
but the server-side HTML response also embeds a JSON-LD JobPosting with full
title/company/location/description fields — that's our extraction path.

When JSON-LD is missing, there's no reliable DOM fallback (the page body is
just a React shell). Return an empty description and let Stage 3 drop the job.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from dajs.extractors._jsonld import extract_from_jsonld
from dajs.extractors.base import ExtractedJob

log = logging.getLogger(__name__)


def _org_from_url(url: str) -> str:
    parts = [p for p in urlparse(url).path.split("/") if p]
    return parts[0] if parts else ""


def extract(html: str, url: str) -> ExtractedJob:
    via_jsonld = extract_from_jsonld(html)
    if via_jsonld and (via_jsonld.get("description") or "").strip():
        # Prefer URL-derived tenant slug over JSON-LD hiringOrganization.name
        # for the same reason as Lever — tenant-managed strings can be wrong.
        via_jsonld["company"] = _org_from_url(url) or via_jsonld.get("company", "")
        return via_jsonld

    log.warning("Ashby: no JSON-LD JobPosting on %s; cannot extract (SPA)", url)
    return ExtractedJob(
        title="",
        company=_org_from_url(url),
        location="",
        description="",
        department=None,
        employment_type=None,
        compensation=None,
        posted_date=None,
    )
