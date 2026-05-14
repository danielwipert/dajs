"""Stage 2 — Hard filters.

Three sequential filters, cheapest first (spec §3.1):
  1. ATS allowlist — apply_url must contain a known-ATS substring
  2. Location     — must match Chicago / Austin / Remote patterns and not be blocked
  3. Dedup        — drop anything already in seen_jobs history

Each filter logs counts; failures are silent drops, not exceptions.
"""

from __future__ import annotations

import logging

from dajs.schemas import ATSPlatform, FilteredJob, LocationCategory, RawJob
from dajs.utils import make_job_id

log = logging.getLogger(__name__)


def _ats_match(url: str, ats_allowlist: dict[str, list[str]]) -> ATSPlatform | None:
    """Return the ATSPlatform whose URL pattern matches, or None."""
    low = url.lower()
    for platform_name, patterns in ats_allowlist.items():
        if any(p.lower() in low for p in patterns):
            return ATSPlatform(platform_name)
    return None


_LOCATION_UNKNOWN = "__unknown__"


def _location_match(
    loc: str,
    location_allowlist: dict[str, list[str]],
    location_blocklist: list[str],
) -> LocationCategory | str | None:
    """Return LocationCategory if loc matches an approved category, the
    _LOCATION_UNKNOWN sentinel if loc is empty (defer to Phase 3 enrichment),
    or None if loc is present but doesn't match any approved category.

    Blocklist defends against false positives like 'Austin Office, San Francisco
    preferred'. Remote is exempt from blocklist (remote-with-SF-office is fine).
    """
    if not loc:
        return _LOCATION_UNKNOWN

    low = loc.lower()

    for kw in location_allowlist.get("remote", []):
        if kw in low:
            return LocationCategory.REMOTE

    blocked = any(b in low for b in location_blocklist)
    if blocked:
        return None

    for category_name, keywords in location_allowlist.items():
        if category_name == "remote":
            continue
        if any(kw in low for kw in keywords):
            return LocationCategory(category_name)

    return None


def filter_by_ats(jobs: list[RawJob], ats_allowlist: dict[str, list[str]]) -> list[tuple[RawJob, ATSPlatform]]:
    survivors: list[tuple[RawJob, ATSPlatform]] = []
    for job in jobs:
        platform = _ats_match(str(job.apply_url), ats_allowlist)
        if platform is not None:
            survivors.append((job, platform))
    log.info("ATS filter: %d → %d", len(jobs), len(survivors))
    return survivors


def filter_by_location(
    pairs: list[tuple[RawJob, ATSPlatform]],
    location_allowlist: dict[str, list[str]],
    location_blocklist: list[str],
) -> list[tuple[RawJob, ATSPlatform, LocationCategory | None]]:
    """Approved/Remote → keep with category; unknown → keep with None (Phase 3
    backstops); explicit non-match → drop."""
    survivors: list[tuple[RawJob, ATSPlatform, LocationCategory | None]] = []
    unknowns = 0
    for job, platform in pairs:
        cat = _location_match(job.location, location_allowlist, location_blocklist)
        if cat is None:
            continue
        if cat == _LOCATION_UNKNOWN:
            survivors.append((job, platform, None))
            unknowns += 1
        else:
            survivors.append((job, platform, cat))
    log.info(
        "Location filter: %d → %d (%d unknown, deferred to Phase 3)",
        len(pairs), len(survivors), unknowns,
    )
    return survivors


def filter_by_dedup(
    triples: list[tuple[RawJob, ATSPlatform, LocationCategory]],
    seen: dict[str, str],
) -> list[FilteredJob]:
    survivors: list[FilteredJob] = []
    for job, platform, cat in triples:
        jid = make_job_id(job.company, job.title, str(job.apply_url))
        if jid in seen:
            continue
        survivors.append(
            FilteredJob(
                **job.model_dump(),
                job_id=jid,
                ats_platform=platform,
                location_category=cat,
            )
        )
    log.info("Dedup filter: %d → %d", len(triples), len(survivors))
    return survivors


def run_filters(jobs: list[RawJob], state: dict, filters_config: dict) -> list[FilteredJob]:
    """End-to-end hard filtering: ATS → location → dedup."""
    ats = filter_by_ats(jobs, filters_config["ats_allowlist"])
    located = filter_by_location(
        ats,
        filters_config["location_allowlist"],
        filters_config.get("location_blocklist", []),
    )
    deduped = filter_by_dedup(located, state["seen"])
    log.info("Stage 2 total: %d raw → %d filtered", len(jobs), len(deduped))
    return deduped
