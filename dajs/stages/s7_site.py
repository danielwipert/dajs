"""Stage 7 — Site generation.

Renders the static `docs/index.html` page from `state/daily_results.json`
using `templates/index.html.j2`. Day keys are sorted descending; jobs within
a day are sorted descending by final_composite_score (already enforced
upstream but we re-sort defensively here).

Spec §7.1, §7.2.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"
DOCS_DIR = REPO_ROOT / "docs"
INDEX_HTML = DOCS_DIR / "index.html"

_LOCATION_LABELS = {
    "chicago": "Chicago",
    "austin": "Austin",
    "remote": "Remote",
}


def _score_band_class(score: float, bands: dict[str, float]) -> str:
    if score >= bands.get("green", 85):
        return "score-band-green"
    if score >= bands.get("blue", 75):
        return "score-band-blue"
    if score >= bands.get("amber", 70):
        return "score-band-amber"
    return "score-band-mute"


def _format_day(d: str) -> str:
    try:
        return datetime.fromisoformat(d).strftime("%A, %B %d, %Y").replace(" 0", " ")
    except ValueError:
        return d


def _job_view(raw: dict, bands: dict[str, float]) -> dict:
    score = float(raw.get("final_composite_score", 0))
    cat = (raw.get("location_category") or "").lower()
    return {
        "title": raw.get("title", ""),
        "company": raw.get("company", ""),
        "location_display": _LOCATION_LABELS.get(cat, raw.get("location") or "—"),
        "ats_platform": raw.get("ats_platform", ""),
        "apply_url": raw.get("apply_url", ""),
        "rationale": raw.get("rationale", ""),
        "role_fit_score": raw.get("role_fit_score", 0),
        "experience_match_score": raw.get("experience_match_score", 0),
        "mission_fit_score": raw.get("mission_fit_score", 0),
        "seniority_match_score": raw.get("seniority_match_score", 0),
        "score_display": f"{score:.1f}",
        "score_band_class": _score_band_class(score, bands),
    }


def render_site(daily_results: dict, scoring_config: dict) -> str:
    """daily_results is the {date_iso: [job_dict, ...]} structure persisted in
    state/daily_results.json. Returns the rendered HTML string."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    template = env.get_template("index.html.j2")

    bands = scoring_config.get("score_bands", {"green": 85, "blue": 75, "amber": 70})
    retention_days = scoring_config.get("site_retention_days", 7)

    # Sort day keys descending so today is on top.
    day_order = sorted(daily_results.keys(), reverse=True)
    days = []
    for d in day_order:
        jobs = sorted(
            daily_results[d],
            key=lambda j: j.get("final_composite_score", 0),
            reverse=True,
        )
        days.append({
            "label": _format_day(d),
            "jobs": [_job_view(j, bands) for j in jobs],
        })

    return template.render(
        days=days,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        retention_days=retention_days,
    )


def write_site(daily_results: dict, scoring_config: dict) -> Path:
    html = render_site(daily_results, scoring_config)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_HTML.write_text(html, encoding="utf-8")
    return INDEX_HTML
