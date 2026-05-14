"""Stage 1 — Search.

Builds the boolean query from configured keywords and asks the SearchProvider
for raw job postings. Pure orchestration; no provider knowledge.
"""

from __future__ import annotations

import logging

from dajs.providers.search_base import SearchProvider
from dajs.providers.serpapi import build_query, site_hosts_from_ats_allowlist
from dajs.schemas import RawJob

log = logging.getLogger(__name__)


def run_search(
    provider: SearchProvider,
    search_config: dict,
    filters_config: dict,
) -> list[RawJob]:
    """Run one search call restricted to the ATS allowlist via site: operators.

    Returns parsed RawJob list.
    """
    site_hosts = site_hosts_from_ats_allowlist(filters_config["ats_allowlist"])
    query = build_query(search_config["keywords"], site_hosts=site_hosts)
    params = search_config.get("serpapi", {})

    log.info(
        "Stage 1: %d keywords × %d ATS hosts",
        len(search_config["keywords"]), len(site_hosts),
    )
    jobs = provider.search(query, params)
    log.info("Stage 1: provider returned %d raw jobs", len(jobs))
    return jobs
