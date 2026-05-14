"""Dover job-page extractor.

Dover's app.dover.com/jobs pages embed structured Next.js data in
__NEXT_DATA__ rather than JSON-LD. We try JSON-LD first (sometimes present),
then fall back to extracting from __NEXT_DATA__, then to the SPA shell.

UNTESTED against a live URL — no Dover posting in the first Phase 2 search
batch. Verify and tighten when one appears.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from dajs.extractors._jsonld import _strip_html, extract_from_jsonld
from dajs.extractors.base import ExtractedJob

log = logging.getLogger(__name__)

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)


def _company_from_url(url: str) -> str:
    parts = [p for p in urlparse(url).path.split("/") if p]
    return parts[1] if len(parts) >= 2 and parts[0] == "jobs" else ""


def _from_next_data(html: str) -> ExtractedJob | None:
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        blob = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    props = blob.get("props", {}).get("pageProps", {})
    job: Any = props.get("job") or props.get("posting")
    if not isinstance(job, dict):
        return None
    return ExtractedJob(
        title=job.get("title") or "",
        company=(job.get("company") or {}).get("name") if isinstance(job.get("company"), dict) else "",
        location=job.get("location") or "",
        description=_strip_html(job.get("description") or ""),
        department=job.get("department"),
        employment_type=job.get("employmentType"),
        compensation=None,
        posted_date=job.get("createdAt") or job.get("postedAt"),
    )


def extract(html: str, url: str) -> ExtractedJob:
    via_jsonld = extract_from_jsonld(html)
    if via_jsonld and (via_jsonld.get("description") or "").strip():
        return via_jsonld

    via_next = _from_next_data(html)
    if via_next and (via_next.get("description") or "").strip():
        if not via_next.get("company"):
            via_next["company"] = _company_from_url(url)
        return via_next

    log.warning("Dover: no JSON-LD or __NEXT_DATA__ on %s; SPA shell only", url)
    soup = BeautifulSoup(html, "lxml")
    title_el = soup.select_one("h1")
    return ExtractedJob(
        title=title_el.get_text(strip=True) if title_el else "",
        company=_company_from_url(url),
        location="",
        description="",
        department=None,
        employment_type=None,
        compensation=None,
        posted_date=None,
    )
