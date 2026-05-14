"""DAJS orchestrator entry point.

Phase 2: Stage 1 (real SerpAPI search) + Stage 2 (hard filters) + Stage 6 (state).
Persists dedup + writes _debug_*.json snapshots so we can inspect each stage.

CLI:
  python -m dajs.run                  # normal run
  python -m dajs.run --reset-state    # clear seen_jobs before running (dev)
  python -m dajs.run --use-stubs      # offline: skip SerpAPI, use canned fixture
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path

import yaml
from dotenv import load_dotenv

from dajs.providers.search_base import SearchProvider
from dajs.providers.stub_llm import StubLLMProvider
from dajs.providers.stub_search import StubSearchProvider
from dajs.stages import s2_filter, s6_state
from dajs.stages.s1_search import run_search
from dajs.stages.s3_enrich import run_enrich


CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
STATE_DIR = Path(__file__).resolve().parent.parent / "state"
DEBUG_FILTERED = STATE_DIR / "_debug_filtered.json"
DEBUG_ENRICHED = STATE_DIR / "_debug_enriched.json"


def load_configs() -> dict:
    configs: dict[str, dict] = {}
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        configs[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return configs


def _build_search_provider(use_stubs: bool, filters_cfg: dict) -> SearchProvider:
    if use_stubs:
        return StubSearchProvider()
    # Lazy import so a missing key only errors when actually running live
    from dajs.providers.serpapi import SerpAPIProvider, site_hosts_from_ats_allowlist

    site_hosts = site_hosts_from_ats_allowlist(filters_cfg["ats_allowlist"])
    return SerpAPIProvider(site_hosts=site_hosts)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="dajs", description="Dan's AI Job Search pipeline")
    p.add_argument(
        "--reset-state",
        action="store_true",
        help="Clear seen_jobs before running (dev convenience)",
    )
    p.add_argument(
        "--use-stubs",
        action="store_true",
        help="Use stub providers instead of live APIs (offline dev)",
    )
    return p.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    load_dotenv()
    args = parse_args()
    configs = load_configs()
    today = date.today().isoformat()

    state = s6_state.load_state()
    if args.reset_state:
        s6_state.reset_seen(state)
        print("[reset] cleared seen_jobs dedup history")
    state["seen"] = s6_state.prune_old_seen(
        state["seen"], days=configs["filters"].get("dedup_prune_days", 90)
    )

    search_provider = _build_search_provider(args.use_stubs, configs["filters"])
    llm_provider = StubLLMProvider()  # Phase 4 swaps this

    print()
    print(f"DAJS run — {today}")
    print(f"  search:   {type(search_provider).__name__}")
    print(f"  llm:      {type(llm_provider).__name__}")
    print(f"  seen:     {len(state['seen'])} entries in dedup history")
    print()

    # Stage 1
    raw_jobs = run_search(search_provider, configs["search"], configs["filters"])
    print(f"Stage 1 — search:   {len(raw_jobs)} raw jobs")

    # Stage 2 — hard filters (ATS + tentative location + dedup)
    filtered = s2_filter.run_filters(raw_jobs, state, configs["filters"])
    print(f"Stage 2 — filters:  {len(filtered)} survived")

    DEBUG_FILTERED.parent.mkdir(parents=True, exist_ok=True)
    DEBUG_FILTERED.write_text(
        json.dumps([j.model_dump(mode="json") for j in filtered], indent=2),
        encoding="utf-8",
    )

    # Stage 3 — enrich (fetch ATS pages + extract + post-enrich location backstop)
    enriched = run_enrich(filtered, configs["filters"])
    print(f"Stage 3 — enrich:   {len(enriched)} enriched")

    DEBUG_ENRICHED.write_text(
        json.dumps([j.model_dump(mode="json") for j in enriched], indent=2),
        encoding="utf-8",
    )

    # Stamp dedup ONLY for jobs that survived enrichment, so fetch failures
    # remain eligible for retry tomorrow (spec §4.4).
    s6_state.add_seen_jobs(state["seen"], [j.job_id for j in enriched], today=today)
    s6_state.save_state(state)

    print()
    print(f"Wrote {DEBUG_FILTERED} ({len(filtered)} jobs)")
    print(f"Wrote {DEBUG_ENRICHED} ({len(enriched)} jobs)")
    print(f"Updated state/seen_jobs.json ({len(state['seen'])} total)")


if __name__ == "__main__":
    main()
