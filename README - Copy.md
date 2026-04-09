<div align="center">

# 🛡️ AI Git Guard

**AI-Powered GitHub Advanced Security Agent**

*Dependabot · Code Scanning · Secret Scanning — analysed by LLM in plain English*

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)]()
[![Version](https://img.shields.io/badge/version-0.2.0-orange.svg)]()

</div>

---

## Overview

**AI Git Guard** is a Python-based interactive terminal tool that connects to the GitHub Advanced Security (GHAS) REST API, fetches all security alerts across your organisation (or a single repository), and uses a Large Language Model to analyse, triage, and explain risks in plain English.

It is designed for **security engineers**, **DevSecOps teams**, and **engineering managers** who need fast, AI-assisted insight into their GitHub security posture — without switching between multiple dashboards.

---

## Key Features

| Module | ID | Description |
|--------|----|-------------|
| Alert Triage & Prioritization | M1 | Ranks open alerts by severity, CVE score, and exploitability |
| Code Remediation Generator | M2 | Provides upgrade commands and fix guidance per vulnerability |
| Natural Language Query Engine | M3 | Answers free-form questions about your alerts in plain English |
| Security Posture Narrator | M6 | Generates an executive briefing suitable for CISO / management |

**Output formats:** Plain text · PDF · HTML · Excel (XLSX) · Weekly Org Report (XLSX) · Enterprise Inventory (XLSX)

**LLM providers:** Ollama (local, zero-cost) · Claude (Anthropic) · OpenAI GPT-4o

---

## How Data Fetching Works

Understanding the data pipeline is important for both usage and troubleshooting. The diagram below shows how alert data flows from GitHub to your screen.

### Data Flow

```
┌───────────────────────────────────┐
│         GitHub REST API v3        │
│  (github.com or GitHub Enterprise)│
└──────────────┬────────────────────┘
               │  Authenticated HTTPS (Bearer token)
               │  Paginated requests (100 items/page)
               │  Automatic rate-limit back-off
               ▼
┌───────────────────────────────────┐
│       github/client.py            │
│  GitHubClient — httpx-based       │
│  Fetches 3 alert categories:      │
│   • Dependabot alerts             │
│   • Code Scanning alerts          │
│   • Secret Scanning alerts        │
└──────────────┬────────────────────┘
               │  Raw JSON responses
               ▼
┌───────────────────────────────────┐
│       github/cache.py             │
│  AlertCache — SQLite-backed       │
│   • Stores raw JSON on disk       │
│   • Key-value with TTL expiry     │
│   • File: .alert_cache.db         │
└──────────────┬────────────────────┘
               │  Cached or fresh JSON
               ▼
┌───────────────────────────────────┐
│       github/aggregator.py        │
│  Parses raw JSON into Pydantic    │
│  domain models and builds a       │
│  SecuritySummary roll-up          │
└──────────────┬────────────────────┘
               │  Typed domain objects
               ▼
┌───────────────────────────────────┐
│      LLM Analysis Modules         │
│  M1 Triage · M2 Remediation       │
│  M3 Query  · M6 Narrator          │
│  (alert data sent to LLM prompt)  │
└──────────────┬────────────────────┘
               │  AI-generated analysis
               ▼
┌───────────────────────────────────┐
│      output/renderer.py           │
│  text · PDF · HTML · Excel        │
│  Saved to ./reports/              │
└───────────────────────────────────┘
```

### Step-by-step breakdown

1. **Authentication** — `GitHubClient` uses the `GITHUB_TOKEN` from your `.env` file to authenticate via a Bearer token against the GitHub REST API v3 (supports both github.com and GitHub Enterprise Server).
2. **Fetching** — Three categories of alerts are fetched in order: **Dependabot**, **Code Scanning**, and **Secret Scanning**. Each category uses paginated GET requests (100 items per page) with automatic `Link: <next>` header following.
3. **Rate-limit handling** — If GitHub returns HTTP 403 or 429, the client reads the `X-RateLimit-Reset` header and sleeps until the window resets, then retries automatically.
4. **Caching** — Before every API call, the system checks the local SQLite cache. If a valid (non-expired) entry exists, the cached data is used instead, eliminating redundant API calls.
5. **Parsing** — Raw JSON is normalised into typed Pydantic models (`DependabotAlert`, `CodeScanningAlert`, `SecretScanningAlert`) by the aggregator module. A `SecuritySummary` roll-up is also computed for the dashboard view.
6. **LLM analysis** — The structured alert context is serialised into the LLM prompt. The AI intent router classifies your natural-language question and dispatches it to the appropriate analysis module (M1–M6).
7. **Output** — Results are displayed in the terminal or exported to `./reports/` in the chosen format (PDF, HTML, Excel).

---

## Data Storage & Cache Lifetime

### Where is data stored?

| Artefact | Location | Contents |
|----------|----------|----------|
| **Alert cache** | `ai_git_guard/.alert_cache.db` | SQLite database containing raw GitHub API JSON responses |
| **Generated reports** | `ai_git_guard/reports/` | Exported PDF, HTML, and Excel report files |
| **Configuration** | `ai_git_guard/.env` | Tokens, org name, LLM settings (never committed to Git) |

The cache database (`.alert_cache.db`) is a single SQLite file stored in the project root. It contains a `cache` table with three columns:

| Column | Type | Description |
|--------|------|-------------|
| `key` | TEXT | Cache key (e.g. `dep:my-org:None:open`) — encodes alert type, org, repo, and state |
| `value` | TEXT | JSON-serialised GitHub API response |
| `stored` | REAL | Unix timestamp of when the data was cached |

### How long does cached data last?

The cache operates on a **TTL (Time To Live)** model:

| Setting | Default | Location |
|---------|---------|----------|
| `CACHE_TTL_MINUTES` | **30 minutes** | `.env` file or `config.py` |

**Behaviour:**
- **Within TTL (< 30 min):** Subsequent queries reuse cached data — no API call is made. This means the LLM analyses the same snapshot of alerts for up to 30 minutes.
- **After TTL expires (≥ 30 min):** The stale cache entry is automatically deleted on the next request and a fresh API call is made to fetch current data.
- **Manual refresh:** Use the `/fetch` command in the terminal to force a fresh download at any time, regardless of TTL.

**To change the cache duration**, set `CACHE_TTL_MINUTES` in your `.env` file:

```env
# Examples:
CACHE_TTL_MINUTES=15     # More frequent refresh (15 min)
CACHE_TTL_MINUTES=60     # Less frequent refresh (1 hour)
CACHE_TTL_MINUTES=1440   # Keep for 24 hours (offline/demo use)
```

### Cache lifecycle diagram

```
User query arrives
       │
       ▼
  ┌─────────────────┐     Yes     ┌────────────────┐
  │ Cache entry      │───────────▶│ Return cached   │
  │ exists & fresh?  │            │ data to LLM     │
  └─────────────────┘            └────────────────┘
       │ No
       ▼
  ┌─────────────────┐            ┌────────────────┐
  │ Fetch from       │───────────▶│ Store in cache  │
  │ GitHub API       │            │ with timestamp  │
  └─────────────────┘            └────────────────┘
```

---

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/your-org/ai-git-guard.git
cd ai-git-guard
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — set GITHUB_TOKEN, GITHUB_ORG, LLM_PROVIDER
```

**Minimum required settings in `.env`:**
```env
GITHUB_TOKEN=ghp_your_token_here
GITHUB_ORG=your-org-name
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3
```

### 3. Install Ollama (for zero-cost local LLM)

```bash
# macOS / Linux
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3          # fast, general purpose
# OR
ollama pull codellama:13b   # better for code analysis (needs 16GB+ RAM)
```

---

## Usage

### Command-Line Reference

```bash
# Default — uses org from .env, auto-detects LLM
python main.py

# Override the GitHub organisation
python main.py --org my-other-org

# Scan a specific repository only
python main.py --repo IN-Information-Security/my-repo

# Browse and pick from all accessible organisations
python main.py --list-orgs

# Enable verbose debug logging
python main.py --debug

# Combine options
python main.py --list-orgs --debug
python main.py --org my-org --repo my-org/my-repo --debug

# Show help
python main.py --help
```

### CLI Options Summary

| Flag | Description |
|------|-------------|
| `--org <name>` | Override the GitHub organisation from `.env` |
| `--repo <owner/repo>` | Scan a single repository instead of the full org |
| `--list-orgs` | Fetch all organisations accessible to your token and choose interactively |
| `--debug` | Enable verbose logging (shows HTTP requests, cache hits, etc.) |
| `--help` | Show CLI help and exit |

### LLM Auto-Detection

When you run `python main.py`, the tool automatically scans for configured LLM providers:

| Scenario | Behaviour |
|----------|-----------|
| **1 provider** has valid credentials | Auto-connects without prompting |
| **Multiple providers** have credentials | Shows a numbered menu to choose from |
| **No providers** configured | Prints setup instructions and exits |

Detection per provider:

| Provider | How it's detected |
|----------|-------------------|
| **Ollama** | Pings the local server at `OLLAMA_BASE_URL` |
| **Claude** | Checks for `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` |
| **OpenAI** | Checks for a valid `OPENAI_API_KEY` (ignores placeholder `sk-xxxx`) |
| **Copilot** | Checks for `COPILOT_TOKEN` |

### Organisation Selection (`--list-orgs`)

When launched with `--list-orgs`, the tool fetches all organisations your GitHub token can access and presents them as a numbered list:

```
Available organisations:
  1. cloudreach  -- We believe cloud platforms must drive transformation...
  2. IN-Information-Security
  3. ATOS
  4. GLB-CES-PublicCloud  -- Atos Global CES Public Cloud Organisation

Select organisation [1/2/3/...] (1): 2
✓ Selected organisation: IN-Information-Security
```

> **Note:** If `--org` is also specified, it takes priority and `--list-orgs` is skipped.

### Start the AI Terminal

```bash
python main.py
```

This launches an interactive AI-powered terminal that:
1. Auto-detects and connects to your LLM (Claude, Ollama, OpenAI)
2. Fetches all security alerts from GitHub Advanced Security
3. Shows your alert summary dashboard
4. Waits for your questions or commands

### Ask anything in plain English

```
You: What are my top 5 security risks?
You: How many critical Dependabot alerts are open?
You: Which repository has the most vulnerabilities?
You: Are there any exposed AWS keys?
You: Generate a PDF executive report
You: How do I fix the lodash vulnerability?
You: Give me a prioritised triage of all alerts
```

The AI automatically routes your request to the right analysis module — no need to remember separate commands.

### Interactive Commands (inside the terminal)

| Command | Action |
|---------|--------|
| *Any English question* | AI auto-routes to the right analysis module |
| `/triage` | Run alert triage & prioritization (M1) |
| `/remediate` | Get fix/upgrade guidance (M2) |
| `/narrate` | Generate executive security briefing (M6) |
| `/report pdf` | Export report as PDF |
| `/report html` | Export report as HTML |
| `/report excel` | Export report as Excel |
| `/report weekly` | Generate Weekly Organisation security report (Excel) |
| `/report enterprise` | Generate Enterprise multi-org repository inventory (Excel, requires `--list-orgs`) |
| `/fetch` | Force-refresh alerts from GitHub (bypasses cache) |
| `/help` | Show all available commands |
| `/exit` | Quit |

---

### Weekly Organisation Report (`/report weekly`)

Generates a comprehensive single-org Excel report with 10 professionally formatted sheets:

| Sheet | Contents |
|-------|----------|
| **Executive Summary** | KPIs, total alerts, compliance score, risk level |
| **Analysis & Progress** | 30-day trend analysis, improvement metrics |
| **Top Risks** | Top 50 critical/high severity alerts across all categories |
| **Repository Health** | Per-repo health matrix with alert counts and risk levels |
| **Recommendations** | Auto-generated prioritised remediation recommendations |
| **Repository Risk Pivot** | Pivot table — repos × severity counts |
| **Dependabot Details** | Full Dependabot alert listing with CVE, CVSS, ecosystem |
| **Code Scanning Details** | Code scanning alerts with CWE, rule, severity, file location |
| **Secret Scanning Details** | Exposed secrets with type, state, push protection status |
| **Supply Chain** | Repository-level supply chain health (language, license, visibility) |

```
You: generate weekly report
You: /report weekly
```

### Enterprise Repository Inventory (`/report enterprise`)

Generates a multi-org Excel report showing all repositories and their security health across multiple organisations. **Requires `--list-orgs`** at startup.

| Sheet | Contents |
|-------|----------|
| **Executive Summary** | Cross-org KPIs, total repos, alert breakdowns |
| **All Repositories** | Full repo listing (23 columns) — language, visibility, stars, forks, alerts |
| **Repository Health** | Per-repo health matrix with vulnerability severity breakdown |
| **Organization Risk Pivot** | Pivot table — organisations × total repos, alerts, compliance scores |

```bash
# Start with --list-orgs to enable enterprise report
python main.py --list-orgs

# Then in the interactive terminal:
You: generate enterprise report
You: /report enterprise
```

> **Note:** The enterprise report fetches repos and alerts for **all** organisations discovered during `--list-orgs`, so it may take longer for tokens with access to many organisations.

---

## GitHub Token Permissions

Create a Fine-Grained PAT at: **Settings → Developer Settings → Personal Access Tokens → Fine-Grained**

Required scopes:

| Permission | Type | Required For |
|-----------|------|-------------|
| `security_events` (read) | Repository | Code Scanning + Secret Scanning |
| `repo` (read) | Repository | Repository metadata |
| `read:org` | Organization | Org-level alert APIs |
| `dependabot_alerts` (read) | Repository | Dependabot alerts |

---

## LLM Provider Configuration

Switch LLM by changing one line in `.env`:

```bash
# Local (free, private — recommended for POC)
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3          # or codellama, mistral

# Anthropic Claude (best quality)
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-xxx

# OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxx
```

> **⚠️ Data Privacy:** Cloud LLMs (Claude, OpenAI) will receive alert data as part of the prompt.
> Always use **Ollama** for sensitive or air-gapped environments where data must not leave the machine.

---

## Project Structure

```
ai_git_guard/
├── main.py                    # Top-level entry point
├── config.py                  # Settings singleton (loads .env)
├── models.py                  # Pydantic models for all alert types
├── requirements.txt
├── .env.example
│
├── github/
│   ├── client.py              # GitHub REST API client (pagination, rate limiting)
│   ├── aggregator.py          # Parses raw JSON → domain models + summary
│   └── cache.py               # SQLite-backed alert cache (TTL configurable)
│
├── llm/
│   ├── base.py                # Abstract LLMAdapter interface
│   ├── factory.py             # Returns the right adapter from config
│   ├── ollama_adapter.py      # Ollama (local)
│   ├── claude_adapter.py      # Anthropic Claude
│   └── openai_adapter.py      # OpenAI GPT
│
├── modules/
│   ├── base.py                # Abstract BaseModule
│   ├── router.py              # AI intent router (classifies user input)
│   ├── m1_triage.py           # M1: Alert Triage & Prioritization
│   ├── m2_remediation.py      # M2: Code Remediation Generator
│   ├── m3_query.py            # M3: Natural Language Query Engine (with history)
│   └── m6_narrator.py         # M6: Security Posture Narrator
│
├── output/
│   ├── renderer.py            # text / PDF / HTML / Excel renderers
│   └── excel_reports.py       # Enterprise & Weekly Excel report generators
│
├── cli/
│   └── main.py                # Unified interactive AI terminal
│
├── reports/                   # Generated report files (gitignored)
└── tests/
    ├── test_aggregator.py
    └── test_cache.py
```

---

## Running Tests

```bash
pytest
pytest --cov=. --cov-report=term-missing
```

---

## Roadmap

| Phase | Scope |
|-------|-------|
| **Phase 1** (Current) | Terminal POC · Ollama local LLM · M1, M2, M3, M6 · 4 output formats |
| **Phase 2** | Cloud LLMs (Claude, OpenAI) · M4 Risk Prediction · M5 Workflow Analyzer · Auto-PR |
| **Phase 3** | Web GUI (Streamlit/FastAPI) · Slack/Teams · Multi-org · RBAC |

---

## Security Considerations

| Area | Details |
|------|---------|
| **Token storage** | `GITHUB_TOKEN` lives only in `.env` — never committed to Git (`.gitignore` enforced). |
| **Local LLM** | Ollama keeps all data on your machine — no external transmission. |
| **Cloud LLM** | Claude / OpenAI providers will receive alert data over HTTPS. Review your org's data-sharing policy. |
| **Cache on disk** | `.alert_cache.db` is a local SQLite file. Apply OS-level access controls to protect it. |
| **Report files** | Reports in `./reports/` may contain sensitive alert details — treat as confidential. |

---

<div align="center">

**AI Git Guard v0.2.0** — GitHub Advanced Security Interactive AI Terminal

</div>
