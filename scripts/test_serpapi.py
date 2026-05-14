"""Isolated SerpAPI smoke test — one live call, prints first few results.

Run: python scripts/test_serpapi.py
Burns ~1 SerpAPI search credit. Confirms auth + parsing before integrating.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Allow running from project root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dajs.providers.serpapi import (
    SerpAPIProvider,
    build_query,
    site_hosts_from_ats_allowlist,
)


def main() -> None:
    load_dotenv()

    search_cfg = yaml.safe_load((Path("config") / "search.yaml").read_text(encoding="utf-8"))
    filters_cfg = yaml.safe_load((Path("config") / "filters.yaml").read_text(encoding="utf-8"))

    site_hosts = site_hosts_from_ats_allowlist(filters_cfg["ats_allowlist"])

    provider = SerpAPIProvider(site_hosts=site_hosts)
    query = build_query(search_cfg["keywords"], site_hosts=site_hosts)
    params = search_cfg["serpapi"]

    print(f"Query (truncated): {query[:120]}...")
    print(f"Params: {params}")
    print()

    jobs = provider.search(query, params)
    print(f"Got {len(jobs)} jobs back.")
    print()

    for i, job in enumerate(jobs[:5], 1):
        print(f"[{i}] {job.title} @ {job.company}")
        print(f"    location: {job.location}")
        print(f"    apply:    {job.apply_url}")
        print(f"    posted:   {job.posted_date}")
        print()


if __name__ == "__main__":
    main()
