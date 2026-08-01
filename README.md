# DAJS — Dan's AI Job Search

DAJS is an automated daily job search pipeline that surfaces, filters, and ranks job opportunities. It restricts searches to direct-apply Applicant Tracking System (ATS) platforms (avoiding high-friction aggregators like LinkedIn or Indeed) and evaluates candidates utilizing a cost-efficient, two-tier Large Language Model (LLM) scoring pipeline calibrated against Daniel Wipert's resume.

The pipeline automatically compiles its findings, updates a local tracking state, and generates a static, clean dashboard viewable on GitHub Pages.

---

## 🚀 Core Features

- **Aggregator Bypass:** Utilizes Google search via SerpAPI to find job postings indexed directly on approved ATS domains.
- **Support for One-Page-Apply ATS Platforms:**
  - [Greenhouse](https://www.greenhouse.io/)
  - [Lever](https://www.lever.co/)
  - [Ashby](https://www.ashbyhq.com/)
  - [Dover](https://www.dover.com/)
  - [BambooHR](https://www.bamboohr.com/)
  - [Recruitee](https://www.recruitee.com/)
  - [SmartRecruiters](https://www.smartrecruiters.com/)
- **Robust Scrapers (JSON-LD + DOM Fallbacks):** Prioritizes semantic metadata extraction via schema.org JSON-LD scripts, falling back to beautiful HTML parser algorithms.
- **Two-Stage LLM Evaluation:**
  - **Stage 4 (Bulk Scorer):** High-throughput, cost-efficient bulk analysis (DeepSeek) evaluates jobs on role fit, experience match, mission fit, and seniority match.
  - **Stage 5 (Verifier Reviewer):** Top candidates are sent to an advanced reviewer model (Claude 3.5 Sonnet) for final score adjustment and a personalized fit rationale.
- **Static Site Generation:** Generates a static HTML dashboard (`docs/index.html`) using Tailwind CSS with beautiful layout, color-coded score bands, and direct apply links.

---

## 🛠️ System Architecture (The 7 Pipeline Stages)

The pipeline is organized as a series of sequential stages adhering to the "Pipes & Filters" design pattern:

```
[SerpAPI] ──> (Stage 1: Search)
                     │
                     ▼
              (Stage 2: Hard Filters) ──> ATS, Location, Seen Deduplication
                     │
                     ▼
              (Stage 3: Enrichment)   ──> Fetch pages, parse JSON-LD/HTML, re-verify Location
                     │
                     ▼
              (Stage 4: Bulk Score)   ──> DeepSeek scoring (4 dimensions)
                     │
                     ▼
              (Stage 5: Final Review) ──> Claude 3.5 Sonnet verification & rationale
                     │
                     ▼
              (Stage 6: State Mgmt)   ──> Save seen jobs, daily results, and timing/cost run logs
                     │
                     ▼
              (Stage 7: Site Gen)     ──> Render docs/index.html via Jinja2 & Tailwind CSS
```

---

## 📂 Repository Layout

```
.
├── config/                 # YAML configs & plain-text resume
│   ├── filters.yaml        # ATS patterns, location allow/blocklists
│   ├── resume.txt          # Candidate's plain-text resume
│   ├── scoring.yaml        # Model names, thresholds, score bands
│   └── search.yaml         # Keywords & SerpAPI search parameters
├── dajs/                   # Core Python application package
│   ├── extractors/         # Platform-specific scraping & JSON-LD extractors
│   ├── providers/          # Search and LLM adapters (live and stubs)
│   ├── stages/             # Implementations for the 7 pipeline stages
│   ├── run.py              # Central orchestrator CLI entrypoint
│   └── schemas.py          # Strongly-typed Pydantic v2 schemas
├── docs/                   # GitHub Pages destination
│   └── index.html          # Rendered, static dashboard
├── planning/               # Product specs and build plans
├── state/                  # JSON local databases (git-tracked)
│   ├── daily_results.json  # Last 7 days of verified jobs
│   ├── run_log.json        # Execution history, token counts, and cost metrics
│   └── seen_jobs.json      # Deduplication history (retained for 90 days)
├── templates/              # Jinja2 HTML templates
└── tests/                  # Test fixtures and example static pages
```

---

## ⚙️ Configuration & Customization

All parameters are configured via standard files in the `config/` directory:

- **`config/resume.txt`**: Plain text of Daniel Wipert's resume.
- **`config/search.yaml`**: Defines search query terms and SerpAPI control flags (e.g., location, pagination).
- **`config/filters.yaml`**: Houses domain URL substrings for supported ATS platforms and strict location allow/block strings (to avoid false-positive location mappings).
- **`config/scoring.yaml`**: Sets LLM models (OpenRouter endpoints), score threshold limit (defaults to `70`), publication limits, and score-band color settings.

---

## 🖥️ Setup & Execution

### 1. Installation
Ensure Python 3.11+ is installed. Then, create a virtual environment and install the required dependencies:

```bash
# Set up a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Setup
Create a `.env` file in the project root with your API credentials (not needed if running in stub mode):

```env
SERPAPI_KEY=your_serpapi_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

### 3. Execution Modes

#### **A. Offline Development (Stub Mode)**
Highly recommended for local development and smoke-testing. Executes the complete 7-stage pipeline end-to-end using canned data, completely bypassing SerpAPI and OpenRouter networks (saving credits and cost):

```bash
python -m dajs.run --use-stubs
```

#### **B. Production Mode (Live APIs)**
Executes the live search, fetches active ATS listings, queries OpenRouter, and updates the local state + rendered dashboard:

```bash
python -m dajs.run
```

#### **C. Development State Reset**
To test parsing and deduplication behaviors without the state memory filters, run with the reset state flag:

```bash
python -m dajs.run --use-stubs --reset-state
```

---

## 📈 Monitoring & Maintenance

- **`state/run_log.json`**: Inspect this file after a live run to view API transaction costs, exact token usage, pipeline step timing, and warnings/errors.
- **`state/seen_jobs.json`**: Tracks seen job listings so that they are never processed more than once. Pruning occurs automatically on a rolling 90-day window.
- **`state/daily_results.json`**: Feeds the static site and retains jobs for a sliding 7-day period.

---

## 📝 License
Proprietary. All rights reserved. Developed by Daniel Wipert (Chorus AI Systems).
