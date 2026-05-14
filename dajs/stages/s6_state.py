"""Stage 6 — State persistence.

Reads and writes the three JSON files that make up DAJS's permanent state.
Spec §6.2.

State files:
  state/seen_jobs.json    {job_id: "YYYY-MM-DD"}    — dedup history, pruned at 90 days
  state/daily_results.json {"YYYY-MM-DD": [PublishedJob,...]} — site source, kept 7 days
  state/run_log.json      [{"date":..., "counts":..., "errors":...}] — audit trail
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

STATE_DIR = Path(__file__).resolve().parent.parent.parent / "state"
SEEN_FILE = STATE_DIR / "seen_jobs.json"
RESULTS_FILE = STATE_DIR / "daily_results.json"
RUN_LOG_FILE = STATE_DIR / "run_log.json"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log.warning("Corrupt state file %s (%s); starting fresh", path.name, e)
        return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def load_state() -> dict[str, Any]:
    """Load all three state files into one dict."""
    return {
        "seen": _load_json(SEEN_FILE, {}),
        "results": _load_json(RESULTS_FILE, {}),
        "runs": _load_json(RUN_LOG_FILE, []),
    }


def save_state(state: dict[str, Any]) -> None:
    _save_json(SEEN_FILE, state["seen"])
    _save_json(RESULTS_FILE, state["results"])
    _save_json(RUN_LOG_FILE, state["runs"])


def add_seen_jobs(seen: dict[str, str], job_ids: list[str], today: str | None = None) -> dict[str, str]:
    """Stamp each new job_id with today's date. Existing IDs are not touched."""
    today = today or date.today().isoformat()
    for jid in job_ids:
        seen.setdefault(jid, today)
    return seen


def prune_old_seen(seen: dict[str, str], days: int = 90) -> dict[str, str]:
    """Drop entries older than `days`. Returns the same dict mutated."""
    cutoff = date.today() - timedelta(days=days)
    stale = [jid for jid, ts in seen.items() if _parse_iso(ts) < cutoff]
    for jid in stale:
        del seen[jid]
    if stale:
        log.info("Pruned %d seen-job entries older than %d days", len(stale), days)
    return seen


def prune_old_results(results: dict[str, list], days: int = 7) -> dict[str, list]:
    """Drop day-keyed results older than `days`."""
    cutoff = date.today() - timedelta(days=days)
    stale = [d for d in results if _parse_iso(d) < cutoff]
    for d in stale:
        del results[d]
    if stale:
        log.info("Pruned %d daily-result entries older than %d days", len(stale), days)
    return results


def append_run_log(runs: list[dict], entry: dict) -> list[dict]:
    runs.append(entry)
    return runs


def reset_seen(state: dict[str, Any]) -> dict[str, Any]:
    """Clear the dedup history (dev convenience for --reset-state)."""
    state["seen"] = {}
    return state


def _parse_iso(s: str) -> date:
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        # Treat unparseable timestamps as ancient so they get pruned.
        return date.min
