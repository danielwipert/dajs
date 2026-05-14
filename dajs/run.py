"""DAJS orchestrator entry point.

Phases 1-4: Stage 1 (search) → Stage 2 (hard filters) → Stage 3 (enrich) →
Stage 4 (bulk score) → Stage 5 (final review). Persists state, writes
daily_results.json, appends run_log.json.

CLI:
  python -m dajs.run                  # normal run
  python -m dajs.run --reset-state    # clear seen_jobs before running (dev)
  python -m dajs.run --use-stubs      # offline: skip live APIs (uses stubs)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Windows defaults stdout/stderr to cp1252 which can't encode the unicode arrow
# and em-dash characters we use in status output. Force UTF-8 if available.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

from dajs.providers.llm_base import LLMProvider
from dajs.providers.search_base import SearchProvider
from dajs.providers.stub_llm import StubLLMProvider
from dajs.providers.stub_search import StubSearchProvider
from dajs.stages import s2_filter, s4_score, s5_review, s6_state, s7_site
from dajs.stages.s1_search import run_search
from dajs.stages.s3_enrich import run_enrich


CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
STATE_DIR = Path(__file__).resolve().parent.parent / "state"
DEBUG_FILTERED = STATE_DIR / "_debug_filtered.json"
DEBUG_ENRICHED = STATE_DIR / "_debug_enriched.json"
DEBUG_SCORED = STATE_DIR / "_debug_scored.json"


def load_configs() -> dict:
    configs: dict[str, dict] = {}
    for path in sorted(CONFIG_DIR.glob("*.yaml")):
        configs[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return configs


def _build_search_provider(use_stubs: bool, filters_cfg: dict) -> SearchProvider:
    if use_stubs:
        return StubSearchProvider()
    from dajs.providers.serpapi import SerpAPIProvider, site_hosts_from_ats_allowlist

    site_hosts = site_hosts_from_ats_allowlist(filters_cfg["ats_allowlist"])
    return SerpAPIProvider(site_hosts=site_hosts)


def _build_llm_provider(use_stubs: bool) -> LLMProvider:
    if use_stubs:
        return StubLLMProvider()
    from dajs.providers.openrouter import OpenRouterProvider

    return OpenRouterProvider()


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="dajs", description="Dan's AI Job Search pipeline")
    p.add_argument("--reset-state", action="store_true",
                   help="Clear seen_jobs before running (dev convenience)")
    p.add_argument("--use-stubs", action="store_true",
                   help="Use stub providers instead of live APIs (offline dev)")
    return p.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    load_dotenv()
    args = parse_args()
    configs = load_configs()
    today = date.today().isoformat()
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    state = s6_state.load_state()
    if args.reset_state:
        s6_state.reset_seen(state)
        print("[reset] cleared seen_jobs dedup history")
    state["seen"] = s6_state.prune_old_seen(
        state["seen"], days=configs["filters"].get("dedup_prune_days", 90)
    )
    state["results"] = s6_state.prune_old_results(
        state["results"], days=configs["scoring"].get("site_retention_days", 7)
    )

    search_provider = _build_search_provider(args.use_stubs, configs["filters"])
    llm_provider = _build_llm_provider(args.use_stubs)

    print()
    print(f"DAJS run — {today}")
    print(f"  search:  {type(search_provider).__name__}")
    print(f"  llm:     {type(llm_provider).__name__}")
    print(f"  seen:    {len(state['seen'])} entries in dedup history")
    print()

    counts: dict[str, int] = {}
    errors: list[str] = []

    # Stage 1
    raw_jobs = run_search(search_provider, configs["search"], configs["filters"])
    counts["raw"] = len(raw_jobs)
    print(f"Stage 1 — search:    {len(raw_jobs)} raw jobs")

    # Stage 2
    filtered = s2_filter.run_filters(raw_jobs, state, configs["filters"])
    counts["filtered"] = len(filtered)
    print(f"Stage 2 — filters:   {len(filtered)} survived")
    _save_json(DEBUG_FILTERED, [j.model_dump(mode="json") for j in filtered])

    # Stage 3
    enriched = run_enrich(filtered, configs["filters"])
    counts["enriched"] = len(enriched)
    print(f"Stage 3 — enrich:    {len(enriched)} enriched")
    _save_json(DEBUG_ENRICHED, [j.model_dump(mode="json") for j in enriched])

    # Stage 4 — bulk score + threshold/top-N
    scored_all = s4_score.run_bulk_score(enriched, llm_provider, configs["scoring"])
    counts["scored"] = len(scored_all)
    advanced = s4_score.filter_and_rank(scored_all, configs["scoring"])
    counts["advanced_to_review"] = len(advanced)
    print(f"Stage 4 — bulk:      {len(scored_all)} scored → {len(advanced)} advanced")
    _save_json(DEBUG_SCORED, [j.model_dump(mode="json") for j in scored_all])

    # Stage 5 — final review
    reviewed = s5_review.run_final_review(advanced, llm_provider, configs["scoring"], today=today)
    counts["reviewed"] = len(reviewed)

    published = s5_review.take_top_for_publication(reviewed, configs["scoring"])
    counts["published"] = len(published)
    print(f"Stage 5 — review:    {len(reviewed)} reviewed → {len(published)} published")

    # Persist day's results — replace today's slot rather than append
    if published:
        state["results"][today] = [j.model_dump(mode="json") for j in published]

    # Stamp dedup for everything that survived enrichment (regardless of
    # whether it was published) — those job_ids represent a permanent decision.
    s6_state.add_seen_jobs(state["seen"], [j.job_id for j in enriched], today=today)

    # Run-log entry
    usage = getattr(llm_provider, "usage", None)
    log_entry = {
        "date": today,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": counts,
        "llm_usage": {
            "calls": usage.calls if usage else 0,
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
            "cost_usd": round(usage.cost_usd, 5) if usage else 0,
            "by_model": usage.by_model if usage else {},
        },
        "errors": errors,
    }
    s6_state.append_run_log(state["runs"], log_entry)
    s6_state.save_state(state)

    # Stage 7 — render the public site
    rendered_path = s7_site.write_site(state["results"], configs["scoring"])
    print(f"Stage 7 — site:      wrote {rendered_path.relative_to(Path.cwd()) if rendered_path.is_relative_to(Path.cwd()) else rendered_path}")

    print()
    print(f"daily_results.json: {sum(len(v) for v in state['results'].values())} jobs across {len(state['results'])} days")
    print(f"seen_jobs.json:     {len(state['seen'])} total")
    print(f"LLM usage:          {log_entry['llm_usage']['calls']} calls, "
          f"{log_entry['llm_usage']['total_tokens']} tokens, "
          f"${log_entry['llm_usage']['cost_usd']}")


if __name__ == "__main__":
    main()
