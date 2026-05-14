"""Greenhouse job-page extractor.

Two hosts both serve the same DOM shape:
  - boards.greenhouse.io/<org>/jobs/<id>      (legacy embed page)
  - job-boards.greenhouse.io/<org>/jobs/<id>  (modern hosted page)

Neither version embeds JSON-LD as of late-2025. We parse the HTML:
  - title:    first <h1>
  - location: .job__location  (modern) or #header .location (legacy)
  - body:     #content div (both versions)
  - company:  derived from URL path (first path segment after host)
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from dajs.extractors.base import ExtractedJob

log = logging.getLogger(__name__)


def _company_from_url(url: str) -> str:
    path = urlparse(url).path or ""
    parts = [p for p in path.split("/") if p]
    return parts[0] if parts else ""


def extract(html: str, url: str) -> ExtractedJob:
    soup = BeautifulSoup(html, "lxml")

    title_el = soup.select_one("h1.app-title") or soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else ""

    loc_el = (
        soup.select_one(".job__location")
        or soup.select_one("#header .location")
        or soup.select_one("div.location")
    )
    location = loc_el.get_text(strip=True) if loc_el else ""

    content_el = (
        soup.select_one("#content")
        or soup.select_one("div.app-content")
        or soup.select_one("div.job__description")
    )
    description = content_el.get_text(separator="\n", strip=True) if content_el else ""

    return ExtractedJob(
        title=title,
        company=_company_from_url(url),
        location=location,
        description=description,
        department=None,
        employment_type=None,
        compensation=None,
        posted_date=None,
    )
