"""Stage 3 — Enrichment.

For each FilteredJob: HTTP GET the apply URL, run the per-ATS extractor, and
build an EnrichedJob. Failure handling per spec §4.4: log and skip; do NOT
add the job to dedup history (caller is responsible for not stamping skipped
jobs into seen_jobs).

Also re-applies the location filter on the now-definitive location string
extracted from the ATS page (spec §3.3 location categories: Chicago, Austin,
Remote). Jobs failing the post-enrichment location check are dropped.
"""

from __future__ import annotations

import logging
import time

import requests

from dajs.extractors import extract_job
from dajs.schemas import EnrichedJob, FilteredJob, LocationCategory

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0 Safari/537.36"
)
DEFAULT_TIMEOUT_S = 30
INTER_REQUEST_DELAY_S = 0.5  # be polite to ATS hosts


def _fetch(url: str, timeout: int = DEFAULT_TIMEOUT_S) -> str | None:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, allow_redirects=True)
    except requests.RequestException as e:
        log.warning("fetch failed (%s): %s", url, e)
        return None
    if not r.ok:
        log.warning("fetch HTTP %d for %s", r.status_code, url)
        return None
    return r.text


def _post_enrich_location_match(
    location: str,
    location_allowlist: dict[str, list[str]],
    location_blocklist: list[str],
) -> LocationCategory | None:
    """Definitive location check on the real, ATS-page-derived location string.

    Same semantics as stages.s2_filter._location_match but with no
    'unknown → pass' sentinel: at this point we have the real string and any
    job that doesn't match must be dropped.
    """
    if not location:
        return None
    low = location.lower()

    for kw in location_allowlist.get("remote", []):
        if kw in low:
            return LocationCategory.REMOTE

    if any(b in low for b in location_blocklist):
        return None

    for category_name, keywords in location_allowlist.items():
        if category_name == "remote":
            continue
        if any(kw in low for kw in keywords):
            return LocationCategory(category_name)

    return None


def run_enrich(
    jobs: list[FilteredJob],
    filters_config: dict,
) -> list[EnrichedJob]:
    """Fetch+extract each job, drop fetch/extract failures, drop non-approved
    locations after enrichment."""
    enriched: list[EnrichedJob] = []
    fetch_failures = 0
    extract_failures = 0
    location_drops = 0

    for i, job in enumerate(jobs):
        if i > 0:
            time.sleep(INTER_REQUEST_DELAY_S)

        html = _fetch(str(job.apply_url))
        if html is None:
            fetch_failures += 1
            continue

        try:
            ext = extract_job(html, str(job.apply_url), job.ats_platform)
        except Exception as e:  # noqa: BLE001
            log.warning("extractor crashed on %s (%s): %s", job.apply_url, job.ats_platform, e)
            extract_failures += 1
            continue

        description = (ext.get("description") or "").strip()
        if not description:
            log.info(
                "empty description after extraction; dropping %s (%s)",
                job.apply_url, job.ats_platform,
            )
            extract_failures += 1
            continue

        # Definitive location check on the real ATS-page location.
        page_location = (ext.get("location") or "").strip()
        cat = _post_enrich_location_match(
            page_location,
            filters_config["location_allowlist"],
            filters_config.get("location_blocklist", []),
        )
        if cat is None:
            location_drops += 1
            log.info(
                "post-enrich location drop: %s @ %s (location=%r)",
                job.title, job.company, page_location,
            )
            continue

        # Carry forward extracted fields, falling back to upstream values when missing.
        enriched.append(
            EnrichedJob(
                **job.model_dump(exclude={"location_category", "title", "company", "location"}),
                title=(ext.get("title") or job.title),
                company=(ext.get("company") or job.company),
                location=page_location,
                location_category=cat,
                description=description,
                department=ext.get("department"),
                employment_type=ext.get("employment_type"),
                compensation=ext.get("compensation"),
            )
        )

    log.info(
        "Stage 3 enrich: %d in → %d out (fetch_fail=%d, extract_fail=%d, location_drop=%d)",
        len(jobs), len(enriched), fetch_failures, extract_failures, location_drops,
    )
    return enriched
