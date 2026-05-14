"""Lever job-page extractor.

Lever pages at jobs.lever.co/<org>/<posting-id> embed a JSON-LD JobPosting
with full title/company/location/description, so that's our primary path.
HTML fallback handles the rare missing-JSON-LD case using Lever's known DOM:
  - .posting-headline > h2 (role title)
  - .location (location)
  - .section-wrapper (description blocks)
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from dajs.extractors._jsonld import extract_from_jsonld
from dajs.extractors.base import ExtractedJob

log = logging.getLogger(__name__)


def _org_from_url(url: str) -> str:
    parts = [p for p in urlparse(url).path.split("/") if p]
    return parts[0] if parts else ""


def extract(html: str, url: str) -> ExtractedJob:
    via_jsonld = extract_from_jsonld(html)
    if via_jsonld and (via_jsonld.get("description") or "").strip():
        # Prefer URL-derived tenant slug over JSON-LD hiringOrganization.name:
        # the latter is operator-entered and sometimes left as the literal
        # string "career" (seen on AIFund). The URL tenant slug is canonical.
        via_jsonld["company"] = _org_from_url(url) or via_jsonld.get("company", "")
        return via_jsonld

    log.info("Lever: no JSON-LD JobPosting for %s, falling back to HTML", url)
    soup = BeautifulSoup(html, "lxml")

    title_el = soup.select_one(".posting-headline h2") or soup.select_one("h2")
    location_el = soup.select_one(".location") or soup.select_one(".posting-categories .location")
    sections = soup.select(".section-wrapper") or soup.select(".section")

    description = "\n\n".join(
        s.get_text(separator="\n", strip=True) for s in sections
    ).strip()

    return ExtractedJob(
        title=title_el.get_text(strip=True) if title_el else "",
        company=_org_from_url(url),
        location=location_el.get_text(strip=True) if location_el else "",
        description=description,
        department=None,
        employment_type=None,
        compensation=None,
        posted_date=None,
    )
