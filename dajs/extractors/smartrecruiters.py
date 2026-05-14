"""SmartRecruiters job-page extractor.

SmartRecruiters consistently embeds JSON-LD JobPosting; primary path.
HTML fallback uses the documented job-content container if JSON-LD is absent.

UNTESTED against a live URL — no SmartRecruiters posting in the first Phase 2
search batch. Verify and tighten when one appears.
"""

from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from dajs.extractors._jsonld import extract_from_jsonld
from dajs.extractors.base import ExtractedJob

log = logging.getLogger(__name__)


def extract(html: str, url: str) -> ExtractedJob:
    via_jsonld = extract_from_jsonld(html)
    if via_jsonld and (via_jsonld.get("description") or "").strip():
        return via_jsonld

    log.info("SmartRecruiters: no JSON-LD on %s, trying HTML fallback", url)
    soup = BeautifulSoup(html, "lxml")
    title_el = soup.select_one("h1")
    location_el = soup.select_one("[data-test-id='job-location']") or soup.select_one(".job-location")
    content_el = soup.select_one(".job-content") or soup.select_one("[data-test-id='job-description']")

    return ExtractedJob(
        title=title_el.get_text(strip=True) if title_el else "",
        company="",
        location=location_el.get_text(strip=True) if location_el else "",
        description=content_el.get_text(separator="\n", strip=True) if content_el else "",
        department=None,
        employment_type=None,
        compensation=None,
        posted_date=None,
    )
