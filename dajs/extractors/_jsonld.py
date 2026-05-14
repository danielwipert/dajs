"""Shared JSON-LD JobPosting extractor.

schema.org defines a JobPosting type with stable field names. Many ATS
platforms (Lever, Ashby, SmartRecruiters, Recruitee) embed one as
`<script type="application/ld+json">…</script>` on each job page. When
present, this is by far the cleanest extraction path — no HTML parsing.

Returns None if no JobPosting block is present or parseable.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from dajs.extractors.base import ExtractedJob

log = logging.getLogger(__name__)

_JSONLD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.S | re.I,
)


def _strip_html(s: str) -> str:
    """Render an HTML fragment to plain text, preserving paragraph breaks."""
    if not s:
        return ""
    return BeautifulSoup(s, "lxml").get_text(separator="\n", strip=True)


def _normalize_location(value: Any) -> str:
    """jobLocation can be a dict, a list of dicts, or a plain string."""
    if not value:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_normalize_location(v) for v in value]
        return " / ".join(p for p in parts if p)
    if isinstance(value, dict):
        # Could be a Place with .address.PostalAddress, or a Place with name
        addr = value.get("address")
        if isinstance(addr, dict):
            bits = [
                addr.get("addressLocality"),
                addr.get("addressRegion"),
                addr.get("addressCountry"),
            ]
            joined = ", ".join(str(b) for b in bits if b)
            if joined:
                return joined
        if value.get("name"):
            return str(value["name"])
    return ""


def _employment_type(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    return str(value).replace("_", " ").title()


def find_jobposting(html: str) -> dict | None:
    """Return the first parseable JobPosting dict in the HTML, or None."""
    for raw in _JSONLD_RE.findall(html):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                    return item
            continue
        if isinstance(data, dict):
            graph = data.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        return item
            if data.get("@type") == "JobPosting":
                return data
    return None


def extract_from_jsonld(html: str) -> ExtractedJob | None:
    posting = find_jobposting(html)
    if not posting:
        return None

    org = posting.get("hiringOrganization") or {}
    company = org.get("name") if isinstance(org, dict) else ""

    out: ExtractedJob = {
        "title": (posting.get("title") or "").strip(),
        "company": (company or "").strip(),
        "location": _normalize_location(posting.get("jobLocation")),
        "description": _strip_html(posting.get("description") or ""),
        "employment_type": _employment_type(posting.get("employmentType")),
        "posted_date": (posting.get("datePosted") or None),
        "department": None,
        "compensation": _compensation_from_jobposting(posting),
    }
    return out


def _compensation_from_jobposting(posting: dict) -> str | None:
    """Surface baseSalary if present; many ATSes leave it null."""
    salary = posting.get("baseSalary")
    if not salary or not isinstance(salary, dict):
        return None
    val = salary.get("value")
    if isinstance(val, dict):
        unit = val.get("unitText", "").lower()
        lo = val.get("minValue")
        hi = val.get("maxValue")
        cur = salary.get("currency") or val.get("currency") or "USD"
        if lo and hi:
            return f"{cur} {lo}–{hi} {unit}".strip()
        if val.get("value"):
            return f"{cur} {val['value']} {unit}".strip()
    return None
