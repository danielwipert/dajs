# DAJS — Build Plan v1.0

> **Companion to:** `DAJS_Product_Spec_v1.0.docx`
> **Purpose:** Step-by-step implementation plan, written to be handed to Claude Code (or worked through manually).
> **Approach:** Five sequential phases. Each phase ends with a working, testable artifact. Don't move to the next phase until the previous one is verified end-to-end.

---

## How to Use This Plan

- **Each phase is a milestone.** Don't skip ahead. Each phase produces something runnable that proves the previous work is correct.
- **Each step inside a phase is small.** If a step feels big, it's probably two steps — break it down further before starting.
- **Always test before moving on.** Every phase ends with a "Verify" checklist. Don't proceed until those boxes are checked.
- **Configs are the contract.** When in doubt about a value (a keyword, a threshold, an ATS pattern), it goes in a config file, not in code.

---

## Prerequisites

Before Phase 1, make sure you have:

- [ ] A GitHub account
- [ ] Python 3.11+ installed locally
- [ ] `git` installed and configured
- [ ] A code editor (VS Code recommended for Claude Code integration)
- [ ] A SerpAPI account → grab your API key (free tier is fine)
- [ ] An OpenRouter account → grab your API key
- [ ] Daniel's resume saved as plain text (`.txt`), ready to drop in the repo

---

## Phase 1 — Foundation

**Goal:** Repo skeleton, schemas, configs, and stub providers. Nothing makes real network calls yet. By the end of this phase, you can run the pipeline end-to-end against canned data and see Pydantic-validated objects flow through every stage.

### Step 1.1 — Create the repo

- [ ] Create a new GitHub repo named `dajs` (private)
- [ ] Clone it locally
- [ ] Add a `README.md` with one sentence describing the project
- [ ] Add a `.gitignore` that excludes `__pycache__/`, `.env`, `.venv/`, `*.pyc`

### Step 1.2 — Create the folder structure

Create these empty directories (touch a `.gitkeep` in each to commit them):

```
dajs/
├── config/
├── dajs/
│   ├── providers/
│   ├── stages/
│   └── extractors/
├── state/
├── templates/
└── docs/
```

### Step 1.3 — Set up Python environment

- [ ] Create a virtualenv: `python3 -m venv .venv && source .venv/bin/activate`
- [ ] Create `requirements.txt` with these dependencies:
  ```
  pydantic>=2.0
  pyyaml
  requests
  beautifulsoup4
  lxml
  jinja2
  python-dotenv
  ```
- [ ] Install: `pip install -r requirements.txt`

### Step 1.4 — Define the Pydantic schemas

Create `dajs/schemas.py`. Define five models in this order:

- [ ] `RawJob` — what the search provider returns
- [ ] `FilteredJob` — survives hard filters, gets a `job_id`
- [ ] `EnrichedJob` — has full job description
- [ ] `ScoredJob` — has Stage 4 scoring
- [ ] `PublishedJob` — final form, what gets written to daily_results.json

Also define these enums:
- [ ] `ATSPlatform` (Greenhouse, Lever, Ashby, Dover, BambooHR, Recruitee, SmartRecruiters)
- [ ] `LocationCategory` (Chicago, Austin, Remote)

**Tip:** Each model should inherit from the previous one where possible to avoid duplication.

### Step 1.5 — Create the config files

- [ ] `config/search.yaml` — keywords (the boolean query), SerpAPI parameters
- [ ] `config/filters.yaml` — ATS URL patterns, location strings
- [ ] `config/scoring.yaml` — bulk model name, review model name, score threshold (start at 70), max jobs per day (10)
- [ ] `config/resume.txt` — paste in Daniel's resume as clean plain text

**Example `config/scoring.yaml`:**
```yaml
bulk_model: "deepseek/deepseek-chat"
review_model: "anthropic/claude-sonnet-4"
score_threshold: 70
max_jobs_per_day: 10
review_top_n: 15   # how many top scorers get sent to Stage 5
```

### Step 1.6 — Define the provider Protocol interfaces

- [ ] Create `dajs/providers/search_base.py` with the `SearchProvider` Protocol
- [ ] Create `dajs/providers/llm_base.py` with the `LLMProvider` Protocol

These are just `typing.Protocol` classes with method signatures — no implementations yet.

### Step 1.7 — Build stub providers

Stubs return canned data so you can develop the pipeline without burning API credits.

- [ ] `dajs/providers/stub_search.py` — returns 3-5 hardcoded fake jobs covering a mix of valid and invalid ATS URLs
- [ ] `dajs/providers/stub_llm.py` — returns fake scoring output with predictable scores

### Step 1.8 — Create the orchestrator entry point

- [ ] Create `dajs/run.py` with a `main()` function
- [ ] Wire up the stub providers
- [ ] Have it print "DAJS pipeline initialized" and exit

### ✅ Phase 1 Verification

- [ ] `python -m dajs.run` runs without errors and prints the init message
- [ ] You can import `from dajs.schemas import *` without errors
- [ ] All five Pydantic models instantiate correctly when given valid data
- [ ] Config files load cleanly via `yaml.safe_load()`

---

## Phase 2 — Search and Hard Filters

**Goal:** Real SerpAPI integration. Hard filter logic working. By the end of this phase, you can run the pipeline against live SerpAPI and produce a JSON file of filtered jobs.

### Step 2.1 — Build the SerpAPI provider

- [ ] Create `dajs/providers/serpapi.py` implementing the `SearchProvider` Protocol
- [ ] Read the API key from environment (use `python-dotenv` for local dev)
- [ ] Implement `search(query, params)` that hits `https://serpapi.com/search?engine=google_jobs`
- [ ] Parse the response into a list of `RawJob` objects
- [ ] Handle errors: rate limit, auth failure, empty results

### Step 2.2 — Test SerpAPI in isolation

- [ ] Write a tiny script `scripts/test_serpapi.py` that just makes one call and prints the results
- [ ] Run it with `.env` populated
- [ ] Confirm you see real jobs come back

### Step 2.3 — Build Stage 1 (Search)

- [ ] Create `dajs/stages/s1_search.py`
- [ ] Function signature: `def run_search(provider: SearchProvider, config: dict) -> list[RawJob]`
- [ ] Loads keywords and params from `config/search.yaml`
- [ ] Calls the provider
- [ ] Returns parsed RawJob list

### Step 2.4 — Build the job_id hashing helper

- [ ] Create `dajs/utils.py`
- [ ] Add `make_job_id(company, title, apply_url) -> str` using SHA-256

### Step 2.5 — Build Stage 2 (Hard Filters)

- [ ] Create `dajs/stages/s2_filter.py`
- [ ] Three sub-functions: `filter_by_ats`, `filter_by_location`, `filter_by_dedup`
- [ ] `filter_by_ats` matches `apply_url` against patterns in `filters.yaml`. Returns the matched `ATSPlatform` for each survivor.
- [ ] `filter_by_location` matches `location` string against approved patterns. Returns `LocationCategory`.
- [ ] `filter_by_dedup` loads `state/seen_jobs.json` and drops anything whose `job_id` is already present.
- [ ] Compose into `def run_filters(jobs: list[RawJob], state: dict) -> list[FilteredJob]`

### Step 2.6 — Build the state manager

- [ ] Create `dajs/stages/s6_state.py` (we're doing this early because Stage 2 needs to read it)
- [ ] Functions: `load_state()`, `save_state(state)`, `add_seen_jobs(jobs)`, `prune_old_seen(days=90)`
- [ ] Operates on `state/seen_jobs.json`, `state/daily_results.json`, `state/run_log.json`

### Step 2.7 — Wire it together

- [ ] Update `dajs/run.py` to call: Stage 1 → Stage 2
- [ ] Print the count at each stage (`Found N raw jobs → M after filters`)
- [ ] Save filtered jobs to `state/_debug_filtered.json` so you can inspect
- [ ] Add the new seen IDs to `seen_jobs.json` (but don't commit this yet — see Step 2.8)

### Step 2.8 — Decide on dedup behavior during dev

While testing, you'll want to re-run with the same jobs without them being deduped. Add a `--reset-state` CLI flag that clears seen_jobs.json before running.

### ✅ Phase 2 Verification

- [ ] `python -m dajs.run` makes one real SerpAPI call
- [ ] You see the count drop from raw → filtered as expected
- [ ] All surviving jobs have apply URLs on the approved ATS list
- [ ] All surviving jobs are in Chicago, Austin, or Remote
- [ ] Re-running without `--reset-state` produces zero new jobs (dedup works)
- [ ] `state/seen_jobs.json` is correctly populated

---

## Phase 3 — Enrichment and Extraction

**Goal:** Fetch the full job description from each surviving ATS page. By the end of this phase, every filtered job has its full description attached.

### Step 3.1 — Build the base extractor

- [ ] Create `dajs/extractors/base.py` with a function signature: `extract(html: str, url: str) -> dict`
- [ ] Returns: `{description, department?, employment_type?, compensation?}`

### Step 3.2 — Build per-ATS extractors (one at a time!)

Start with Greenhouse since it's the most common. Get it working end-to-end before starting the next.

- [ ] `dajs/extractors/greenhouse.py` — Greenhouse uses a predictable HTML structure; the job content lives in a div with class `content` or similar. Inspect 2-3 real Greenhouse pages first.
- [ ] `dajs/extractors/lever.py`
- [ ] `dajs/extractors/ashby.py`
- [ ] `dajs/extractors/dover.py`
- [ ] `dajs/extractors/bamboohr.py`
- [ ] `dajs/extractors/recruitee.py`
- [ ] `dajs/extractors/smartrecruiters.py`

**Tip:** For each one, save an example HTML page to `tests/fixtures/<ats>_example.html` so you can re-test extraction without re-fetching.

### Step 3.3 — Build the extractor dispatcher

- [ ] Create `dajs/extractors/__init__.py`
- [ ] Function: `def extract_job(html: str, url: str, ats: ATSPlatform) -> dict`
- [ ] Routes to the correct per-ATS extractor

### Step 3.4 — Build Stage 3 (Enrich)

- [ ] Create `dajs/stages/s3_enrich.py`
- [ ] Function signature: `def run_enrich(jobs: list[FilteredJob]) -> list[EnrichedJob]`
- [ ] For each filtered job: HTTP GET the apply URL (with a real user-agent), pass to dispatcher, build EnrichedJob
- [ ] Failure handling: if fetch or extraction fails, log and skip that job. Do NOT add it to dedup history.

### Step 3.5 — Wire into the orchestrator

- [ ] Update `dajs/run.py` to call: Stage 1 → Stage 2 → Stage 3
- [ ] Save enriched jobs to `state/_debug_enriched.json` for inspection

### ✅ Phase 3 Verification

- [ ] All seven extractors work against real ATS pages
- [ ] Enriched jobs have meaningful description text (not empty, not raw HTML)
- [ ] A single failed fetch doesn't kill the run — other jobs continue
- [ ] Re-run on the same day produces zero new enriched jobs (dedup still working)

---

## Phase 4 — LLM Scoring

**Goal:** Real LLM scoring with OpenRouter. Two-stage: cheap bulk scoring + top-tier final review. By the end of this phase, every enriched job has a composite score and the top scorers have rationales.

### Step 4.1 — Build the OpenRouter provider

- [ ] Create `dajs/providers/openrouter.py` implementing `LLMProvider` Protocol
- [ ] `complete(system, user, model, schema)` — POSTs to `https://openrouter.ai/api/v1/chat/completions`
- [ ] Use structured-output / JSON-mode to enforce the Pydantic schema
- [ ] Handle: rate limit, invalid JSON (single retry), model availability

### Step 4.2 — Test OpenRouter in isolation

- [ ] Write `scripts/test_openrouter.py` that scores one fake job and prints the result
- [ ] Confirm valid JSON comes back matching the schema

### Step 4.3 — Define the scoring schema

- [ ] In `schemas.py`, add `BulkScoringOutput` with: role_fit_score, experience_match_score, mission_fit_score, seniority_match_score, plus a `justifications` dict mapping dimension name → 1-sentence reason

### Step 4.4 — Write the bulk scoring prompt

- [ ] Create `dajs/prompts/bulk_score.py`
- [ ] System message: defines Daniel's profile, the four dimensions, the 0-100 scale, and the required JSON output schema
- [ ] User message template: takes resume + enriched job, returns the prompt string
- [ ] Resume is loaded once from `config/resume.txt` and cached

### Step 4.5 — Build Stage 4 (Bulk Scoring)

- [ ] Create `dajs/stages/s4_score.py`
- [ ] Function: `def run_bulk_score(jobs: list[EnrichedJob], llm: LLMProvider, config: dict) -> list[ScoredJob]`
- [ ] For each enriched job: send to LLM, parse output, compute composite, build ScoredJob
- [ ] Single retry on invalid JSON; drop on second failure (with log)

### Step 4.6 — Filter by threshold

- [ ] After bulk scoring, drop anything below `config.score_threshold`
- [ ] Sort survivors by composite score descending
- [ ] Take top `config.review_top_n` for Stage 5

### Step 4.7 — Define the final review schema and prompt

- [ ] Add `FinalReviewOutput` to schemas: adjusted scores + `rationale` (1-2 sentence "why this fits Daniel" blurb)
- [ ] Create `dajs/prompts/final_review.py`

### Step 4.8 — Build Stage 5 (Final Review)

- [ ] Create `dajs/stages/s5_review.py`
- [ ] Function: `def run_final_review(jobs: list[ScoredJob], llm: LLMProvider, config: dict) -> list[PublishedJob]`
- [ ] Sends top scorers to the review model
- [ ] Builds PublishedJob with final scores + rationale + published_date

### Step 4.9 — Take top N for publication

- [ ] After Stage 5, take the top `config.max_jobs_per_day` for the day

### Step 4.10 — Wire into the orchestrator

- [ ] Update `dajs/run.py` to call: Stage 1 → 2 → 3 → 4 → 5
- [ ] Save published jobs into `state/daily_results.json` under today's date key
- [ ] Update `state/seen_jobs.json` with the published jobs' IDs
- [ ] Write `state/run_log.json` with counts at each stage and total token costs

### ✅ Phase 4 Verification

- [ ] A full run produces a populated `daily_results.json` with today's date as a key
- [ ] Each published job has all four dimension scores, a composite, and a rationale
- [ ] Composite scores all meet or exceed the threshold
- [ ] Jobs are sorted descending by composite within the day
- [ ] `run_log.json` shows counts at each stage and approximate cost
- [ ] Total LLM cost for one daily run is under $0.50 (sanity check)

---

## Phase 5 — Site Generation and Automation

**Goal:** Live, automated, publicly-viewable GitHub Pages site updating daily.

### Step 5.1 — Design the Jinja2 template

- [ ] Create `templates/index.html.j2`
- [ ] Include Tailwind via CDN in the `<head>`
- [ ] Add `<meta name="robots" content="noindex, nofollow">`
- [ ] Layout:
  - Header with site name and last-updated timestamp
  - For each day (descending):
    - Day section header with formatted date
    - List of jobs, each as a card:
      - Composite score badge (top-right of card, color-coded)
      - Role title (large)
      - Company name + location (subtitle)
      - ATS platform pill
      - Rationale (1-2 lines)
      - Four sub-scores (Role / Experience / Mission / Seniority) as a small breakdown
      - "Apply" button → opens apply URL in new tab
- [ ] Empty-state message when a day has zero jobs

### Step 5.2 — Build Stage 7 (Site Generation)

- [ ] Create `dajs/stages/s7_site.py`
- [ ] Function: `def render_site(daily_results: dict) -> str`
- [ ] Loads template, renders with the last 7 days of results, returns HTML string
- [ ] Trim daily_results to last 7 days before rendering

### Step 5.3 — Trim old days from daily_results.json

- [ ] In s6_state.py, add `prune_old_results(days=7)` that removes day keys older than 7 days from daily_results.json

### Step 5.4 — Wire site rendering into orchestrator

- [ ] Update `dajs/run.py` to call render_site after Stage 5
- [ ] Write the rendered HTML to `docs/index.html`

### Step 5.5 — Enable GitHub Pages

- [ ] Repo Settings → Pages
- [ ] Source: Deploy from a branch
- [ ] Branch: `main` / folder: `/docs`
- [ ] Confirm the URL works (will be empty until first run)

### Step 5.6 — Create the GitHub Actions workflow

- [ ] Create `.github/workflows/dajs-daily.yml`
- [ ] Trigger: cron `0 13 * * *` (13:00 UTC = 8:00 AM Central) + `workflow_dispatch`
- [ ] Steps:
  1. Checkout repo with write permissions
  2. Set up Python 3.11
  3. Install dependencies
  4. Run the pipeline (`python -m dajs.run`)
  5. Commit changes back to main with message `DAJS daily update — {date} — {N} jobs published`

### Step 5.7 — Configure secrets

- [ ] Repo Settings → Secrets and variables → Actions → New repository secret
- [ ] Add `SERPAPI_KEY`
- [ ] Add `OPENROUTER_API_KEY`

### Step 5.8 — Test a manual dispatch

- [ ] Actions tab → DAJS daily → Run workflow
- [ ] Watch the run complete
- [ ] Verify commits land on main with state updates
- [ ] Verify the GitHub Pages site renders the new day correctly

### Step 5.9 — Wait for the first automated run

- [ ] Let the cron trigger fire at the scheduled time
- [ ] Confirm everything works end-to-end without manual intervention

### ✅ Phase 5 Verification

- [ ] GitHub Pages site is live at the unlisted URL
- [ ] Site is `noindex` (check the source)
- [ ] Today's jobs render with all expected fields
- [ ] Composite score badges are color-coded correctly
- [ ] Apply buttons open the correct ATS pages in new tabs
- [ ] After 7+ days, the oldest day correctly drops off
- [ ] Cron-triggered run produces commits without manual intervention
- [ ] When a workflow run fails (test this on purpose), GitHub emails you

---

## After Launch

### Tuning the threshold

For the first 1-2 weeks, leave the threshold at 70 and observe. Then adjust based on what you see:

- If the page is mostly empty and good jobs are being dropped → lower the threshold
- If the page is full of marginal jobs → raise the threshold
- If both happen on different days → look at the scoring rubric, not the threshold

### Expanding the keyword set

The query in `config/search.yaml` is the single biggest lever. If you're missing entire categories of jobs:

- Add new title variants to the boolean query
- Make sure new variants don't accidentally pull in low-fit roles (the LLM will mostly filter these out, but every irrelevant job still costs an LLM call)

### Adding a new ATS platform

Three places to update:

1. Add to `ATSPlatform` enum in `schemas.py`
2. Add URL pattern to `config/filters.yaml`
3. Write a new extractor in `dajs/extractors/`

That's it. No other code changes required.

### Cost monitoring

Check `state/run_log.json` weekly. Per-run costs should be small (under $0.50). If they spike:

- Did the search start returning way more jobs?
- Are too many jobs passing hard filters?
- Did the bulk model change?

### When to consider v2

Out-of-scope features for v1 (cover letter generation, application tracking, auto-apply, multi-search) are good v2 candidates IF — and only if — daily v1 usage proves the discovery and ranking work well. Don't build v2 features until v1 has been running cleanly for at least 30 days.

---

## Quick Reference — Phase Checkpoints

| Phase | End-State Artifact |
|---|---|
| 1 | Repo skeleton; stub providers; schemas validate; pipeline runs against canned data |
| 2 | Real SerpAPI search + hard filters; filtered jobs persisted to JSON |
| 3 | Full ATS job descriptions fetched and attached to every filtered job |
| 4 | Two-stage LLM scoring produces published jobs with composite scores and rationales |
| 5 | Live GitHub Pages site updating daily via GitHub Actions |

---

*DAJS Build Plan — v1.0 — Companion to DAJS Product Spec v1.0*
*Chorus AI Systems — Daniel Wipert — May 2026*
