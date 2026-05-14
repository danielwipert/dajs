"""BambooHR job-page extractor.

BambooHR uses tenant subdomains: <org>.bamboohr.com/careers/<id>. Pages
sometimes embed JSON-LD JobPosting; primary path. HTML fallback uses the
documented .BambooHR-ATS-Description container.

UNTESTED against a live URL — no BambooHR posting in the first Phase 2
search batch. Verify and tighten when one appears.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from dajs.extractors._jsonld import extract_from_jsonld
from dajs.extractors.base import ExtractedJob

log = logging.getLogger(__name__)


def _company_from_host(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host.split(".")[0] if host else ""


def extract(html: str, url: str) -> ExtractedJob:
    via_jsonld = extract_from_jsonld(html)
    if via_jsonld and (via_jsonld.get("description") or "").strip():
        if not via_jsonld.get("company"):
            via_jsonld["company"] = _company_from_host(url)
        return via_jsonld

    log.info("BambooHR: no JSON-LD on %s, trying HTML fallback", url)
    soup = BeautifulSoup(html, "lxml")
    title_el = soup.select_one(".BambooHR-ATS-Jobs-Item h2") or soup.select_one("h1")
    location_el = (
        soup.select_one(".BambooHR-ATS-Location")
        or soup.select_one(".js-job-location")
    )
    content_el = (
        soup.select_one(".BambooHR-ATS-Description")
        or soup.select_one("#js-job-description")
    )

    return ExtractedJob(
        title=title_el.get_text(strip=True) if title_el else "",
        company=_company_from_host(url),
        location=location_el.get_text(strip=True) if location_el else "",
        description=content_el.get_text(separator="\n", strip=True) if content_el else "",
        department=None,
        employment_type=None,
        compensation=None,
        posted_date=None,
    )
