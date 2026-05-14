"""Recruitee job-page extractor.

Recruitee uses tenant subdomains: <org>.recruitee.com/o/<slug>. The public
pages typically embed JSON-LD JobPosting; primary path. HTML fallback uses
their standard `.offer__description` container.

UNTESTED against a live URL — no Recruitee posting in the first Phase 2
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

    log.info("Recruitee: no JSON-LD on %s, trying HTML fallback", url)
    soup = BeautifulSoup(html, "lxml")
    title_el = soup.select_one("h1.offer__title") or soup.select_one("h1")
    location_el = soup.select_one(".offer__location") or soup.select_one(".offer-location")
    content_el = soup.select_one(".offer__description") or soup.select_one("[itemprop='description']")

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
