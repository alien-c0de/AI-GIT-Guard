<div align="center">

# 🛡️ AI Git Guard

**AI-Powered GitHub Advanced Security Agent**

*Dependabot · Code Scanning · Secret Scanning — analysed by AI in plain English*

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)]()
[![Version](https://img.shields.io/badge/version-0.2.0-orange.svg)]()

</div>

---

## Table of Contents

- [Overview](#overview)
- [Core Concepts](#core-concepts)
- [Key Features](#key-features)
- [Architecture](#architecture)
  - [Data Pipeline](#data-pipeline)
  - [AI Intelligence Layer](#ai-intelligence-layer)
- [Data Storage & Caching](#data-storage--caching)
- [Quick Start](#quick-start)
- [Configuration Reference](#configuration-reference)
- [Usage](#usage)
- [Output Formats & Reports](#output-formats--reports)
- [GitHub Token Permissions](#github-token-permissions)
- [LLM Provider Configuration](#llm-provider-configuration)
- [Project Structure](#project-structure)
- [Running Tests](#running-tests)
- [Roadmap](#roadmap)
- [Security Considerations](#security-considerations)

---

## Overview

**AI Git Guard** is an interactive, AI-powered security assistant that connects to your GitHub organisation, retrieves all security alerts, and enables natural-language querying — without navigating multiple dashboards or writing scripts.

Designed for **security engineers**, **DevSecOps teams**, and **engineering managers**, it bridges the gap between raw GitHub Advanced Security data and the actionable, human-readable insight your team actually needs.

### Value Proposition

| Without AI Git Guard | With AI Git Guard |
|---|---|
| Hundreds of unranked alerts across multiple dashboards | AI-prioritised list of what to fix first |
| Manual CVE research to understand risk | Instant severity, exploitability, and business impact explanation |
| Fix instructions buried in external advisories | Exact upgrade commands generated per vulnerability |
| Hours spent authoring security reports | One command produces executive-ready PDF, HTML, or Excel output |
| Querying alert data requires scripting or manual filtering | Ask in plain English and receive a structured answer |

---

## Core Concepts

### GitHub Advanced Security (GHAS)

GitHub Advanced Security automatically scans your repositories and surfaces three categories of vulnerability:

| Alert Type | What Is Detected | Example |
|---|---|---|
| **Dependabot** | Vulnerable or outdated third-party dependencies | `lodash 4.17.19` has a known prototype-pollution vulnerability — upgrade to `4.17.21` |
| **Code Scanning** | Security flaws in your own source code (via CodeQL or third-party tools) | Line 42 of `login.py` is vulnerable to SQL injection |
| **Secret Scanning** | API keys, tokens, or passwords accidentally committed to source control | An AWS access key was found in `config.js` — revoke it immediately |

### LLM (Large Language Model)

AI Git Guard integrates with a Large Language Model to interpret your alert data and compose human-readable analysis. It supports four providers: a free local option (Ollama), two commercial cloud APIs (Claude, OpenAI), and a GitHub-native free tier (GitHub Models).

---

## Key Features

| ID | Module | Capability | Example Query |
|---|---|---|---|
| M1 | Alert Triage & Prioritization | Ranks all open alerts by severity, CVSS score, and real-world exploitability | *"What should I fix first?"* |
| M2 | Code Remediation Generator | Produces exact upgrade commands and patch guidance for every vulnerability | *"How do I fix the lodash issue?"* |
| M3 | Natural Language Query Engine | Answers free-form questions about your alerts; maintains a 10-turn conversation context | *"How many critical alerts does repo X have?"* |
| M4 | Risk Prediction Engine | Uses pattern analysis to predict which repositories are most likely to be exploited | *"Which repos are at highest risk?"* |
| M5 | Workflow Security Analyzer | Reviews GitHub Actions YAML workflow files for CI/CD security misconfigurations | *"Are my workflows safe?"* |
| M6 | Security Posture Narrator | Generates an executive briefing suitable for a CISO or board audience | *"Generate a board-level security summary"* |

**Supported output formats:** Terminal (colour-coded) · PDF · HTML · Excel (XLSX) · Weekly Org Report (10-sheet XLSX) · Enterprise Inventory (4-sheet XLSX)

**Supported LLM providers:** Ollama (local, free, private) · Claude (Anthropic) · OpenAI GPT · GitHub Models (free with GitHub token)

---

## Architecture

### Data Pipeline

Alert data flows through five sequential stages before reaching the AI:

```
┌───────────────────────────────────┐
│         GitHub REST API v3        │
│  (github.com or GitHub Enterprise)│
└──────────────┬────────────────────┘
               │  HTTPS — paginated (100 alerts/page)
               │  Automatic rate-limit back-off & retry
               ▼
┌───────────────────────────────────┐
│       github/client.py            │
│  GitHubClient                     │
│  • Dependabot alerts              │
│  • Code Scanning alerts           │
│  • Secret Scanning alerts         │
└──────────────┬────────────────────┘
               │  Raw JSON
               ▼
┌───────────────────────────────────┐
│       github/cache.py             │
│  AlertCache (SQLite)              │
│  • Stores responses with TTL      │
│  • Default TTL: 30 minutes        │
│  • File: .alert_cache.db          │
└──────────────┬────────────────────┘
               │  Cached or fresh JSON
               ▼
┌───────────────────────────────────┐
│       github/aggregator.py        │
│  Parses JSON into typed Pydantic  │
│  models; computes SecuritySummary │
└──────────────┬────────────────────┘
               │  Structured alert objects
               ▼
┌───────────────────────────────────┐
│      Modules M1–M6                │
│  Each module builds an LLM prompt │
│  from the structured data and     │
│  queries the configured provider  │
└──────────────┬────────────────────┘
               │  AI-generated analysis text
               ▼
┌───────────────────────────────────┐
│      output/renderer.py           │
│  Terminal · PDF · HTML · Excel    │
│  Saved to ./reports/              │
└───────────────────────────────────┘
```

**Stage descriptions:**

1. **Authentication** — `GITHUB_TOKEN` (from `.env`) is sent as a Bearer token in every request. GitHub Enterprise Server is supported via `GITHUB_ENTERPRISE_URL`.

2. **Fetching** — All three alert categories are retrieved with 100 items per page. Pagination is followed automatically. On HTTP 429/403, the client reads the `X-RateLimit-Reset` header, sleeps until the window resets, and retries.

3. **Caching** — API responses are stored in a local SQLite database (`.alert_cache.db`). Subsequent queries within the TTL window are served from cache — no API call required. Use `/fetch` to bypass the cache at any time.

4. **Parsing** — Raw JSON is validated and normalised into typed Pydantic v2 models: `DependabotAlert`, `CodeScanningAlert`, `SecretScanningAlert`. An org-wide `SecuritySummary` (total counts, severity breakdown, compliance score) is computed at this stage.

5. **AI Analysis** — Structured alert data is serialised into a detailed prompt and dispatched to the configured LLM. The Intent Router classifies your query (up to 20 tokens) and routes it to the correct specialist module before the full analysis prompt is sent.

---

### AI Intelligence Layer

```
┌─────────────────────────────────────────────────────────────┐
│                         User Input                          │
│           Natural language query  /or/  slash command       │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│          Step 1 — Intent Router  (modules/router.py)        │
│                                                             │
│  Slash command ──▶ Instant mapping (zero AI calls)          │
│  /triage   → M1    /remediate → M2    /risk     → M4        │
│  /workflow → M5    /narrate   → M6    /report   → Renderer  │
│                                                             │
│  Natural language ──▶ LLM classification call              │
│  System: "Classify into one of 10 categories"               │
│  Model reply: single word, max 20 tokens                    │
│  Fallback on failure: M3 (Query)                            │
└──────────────────────────────┬──────────────────────────────┘
                               │  Intent enum + args
                               ▼
┌─────────────────────────────────────────────────────────────┐
│          Step 2 — Module Dispatch  (cli/main.py)            │
│                                                             │
│  TRIAGE      → M1 TriageModule                              │
│  REMEDIATION → M2 RemediationModule                         │
│  QUERY       → M3 NLQueryModule  (maintains history)        │
│  RISK        → M4 RiskPredictionModule                      │
│  WORKFLOW    → M5 WorkflowAnalyzerModule                    │
│  NARRATE     → M6 NarratorModule                            │
│  REPORT      → Renderer (M1/M2/M6 as appropriate)          │
│  FETCH       → Reload alerts, no AI call                   │
└──────────────────────────────┬──────────────────────────────┘
                               │  Alert context dict
                               ▼
┌─────────────────────────────────────────────────────────────┐
│          Step 3 — Prompt Construction                       │
│                                                             │
│  • System persona   (role-specific expert identity)         │
│  • Alert data       (Dependabot, Code Scanning, Secrets)    │
│  • Conversation history  (M3 only — last 10 turns)         │
│  • User query                                               │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│          Step 4 — LLM Adapter  (llm/)                       │
│                                                             │
│  OllamaAdapter        → localhost:11434                     │
│  ClaudeAdapter        → Anthropic API                       │
│  OpenAIAdapter        → OpenAI API                          │
│  GitHubModelsAdapter  → Azure AI inference (GITHUB_TOKEN)   │
│                                                             │
│  All return: LLMResponse { text, model, provider,           │
│              prompt_tokens, completion_tokens }             │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│          Step 5 — Output Renderer  (output/)                │
│                                                             │
│  Terminal   → Rich panels, colour-coded by severity         │
│  PDF        → reportlab                                     │
│  HTML       → built-in template renderer                    │
│  Excel      → openpyxl (weekly: 10 sheets; enterprise: 4)  │
└─────────────────────────────────────────────────────────────┘
```

#### AI Call Budget

| Input Type | AI Calls | Detail |
|---|---|---|
| Slash command (e.g. `/triage`) | **1** | Module is known — no classification required |
| Natural language query | **2** | Call 1: intent classification (≤20 tokens). Call 2: full analysis |
| `/fetch`, `/help`, `/clear` | **0** | Local operations — no LLM involved |

#### Module Personas

Each module configures the LLM with a focused system prompt to ensure consistent, expert-quality output:

| Module | LLM Persona |
|---|---|
| M1 Triage | Senior application security engineer, GitHub Advanced Security expert |
| M2 Remediation | Dependency management and secure software supply chain specialist |
| M3 Query | AI Git Guard — GitHub Advanced Security analyst assistant |
| M4 Risk Prediction | Senior security risk analyst, predictive threat modelling |
| M5 Workflow Analyzer | Senior DevSecOps engineer, GitHub Actions security expert |
| M6 Narrator | Security communications expert writing executive briefings for CISOs |

#### Conversation Context (M3 Query)

The Query module (M3) maintains a rolling 10-turn conversation history. Follow-up questions resolve naturally without repeating context:

```
You: How many critical alerts are there?
AI:  There are 12 critical alerts across 5 repositories.

You: Which ones are easiest to fix?
AI:  Of the 12, the 3 easiest are...

You: Show me just the npm ones.
AI:  Of those 3, 2 are npm packages...
```

All other modules (M1, M2, M4, M5, M6) are stateless — each call is independent.

#### Alert Context Dictionary

Every module receives the same structured data package:

```python
{
    "org":            "my-org",
    "repo":           None,                        # or "owner/repo" if --repo was used
    "dependabot":     [DependabotAlert, ...],
    "code_scanning":  [CodeScanningAlert, ...],
    "secret_scanning":[SecretScanningAlert, ...],
    "summary":        SecuritySummary,
}
```

No module includes `GITHUB_TOKEN` or any other credential in the AI prompt.

---

## Data Storage & Caching

### Storage Locations

| Artefact | Default Path | Contents |
|---|---|---|
| Alert cache | `ai_git_guard/.alert_cache.db` | SQLite database — GitHub API responses |
| Generated reports | `ai_git_guard/reports/` | PDF, HTML, and Excel report files |
| Configuration | `ai_git_guard/.env` | Tokens and settings — never commit to Git |

### SQLite Cache Schema

| Column | Type | Description |
|---|---|---|
| `key` | TEXT (PK) | Cache key, e.g. `dep:my-org:None:open` |
| `value` | TEXT | Full JSON API response |
| `stored` | REAL | Unix timestamp of when the data was stored |

The cache file is created with `0o600` permissions (owner read/write only).

### Cache TTL

| Setting | Default | Where to Set |
|---|---|---|
| `CACHE_TTL_MINUTES` | `30` | `.env` or `config.py` |

```env
CACHE_TTL_MINUTES=15     # Active incident response
CACHE_TTL_MINUTES=60     # Standard daily use
CACHE_TTL_MINUTES=1440   # Offline or demo mode (24 hours)
```

Use `/fetch` inside the interactive terminal to force an immediate cache refresh at any time.

```
You ask a question
       │
       ▼
  ┌────────────────────────────┐   YES   ┌─────────────────────────────┐
  │ Is cached data < TTL?      │────────▶│ Serve from cache — instant  │
  └────────────────────────────┘         └─────────────────────────────┘
       │ NO  (or /fetch used)
       ▼
  ┌────────────────────────────┐         ┌─────────────────────────────┐
  │ Fetch fresh data from      │────────▶│ Save to cache with current  │
  │ GitHub API                 │         │ timestamp                   │
  └────────────────────────────┘         └─────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.10 or newer — [python.org/downloads](https://www.python.org/downloads/)
- A GitHub Personal Access Token with the required scopes — see [GitHub Token Permissions](#github-token-permissions)
- At least one AI provider configured — Ollama is recommended (free, local, no data leaves your machine)

### 1. Clone and Install

```bash
git clone https://github.com/alien-c0de/ai-git-guard.git
cd ai-git-guard

python -m venv .venv

# Activate the virtual environment:
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\activate             # Windows (PowerShell)

pip install -r requirements.txt
```

### 2. Create Your Configuration File

```bash
cp .env.example .env
```

Open `.env` and fill in the required values:

```env
GITHUB_TOKEN=ghp_your_token_here
GITHUB_ORG=your-organisation-name
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3
```

### 3. Install Ollama (Recommended Local AI Provider)

Ollama runs the AI model entirely on your own machine — no API costs, no data transmitted externally.

```bash
# macOS / Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows — download from https://ollama.ai/download
```

Pull a model after installation:

```bash
ollama pull llama3          # ~4 GB — general purpose, fast
ollama pull codellama:13b   # Better for code analysis (requires 16 GB+ RAM)
```

Ollama starts automatically as a background service at `http://localhost:11434`. AI Git Guard detects it on startup.

### 4. Run

```bash
python main.py
```

---

## Configuration Reference

All settings are read from the `.env` file in the project root.

### GitHub Settings

| Variable | Required | Default | Description |
|---|---|---|---|
| `GITHUB_TOKEN` | **Yes** | — | Personal Access Token for GitHub API authentication |
| `GITHUB_ORG` | **Yes** | — | GitHub organisation to scan |
| `GITHUB_ENTERPRISE_URL` | No | — | Base URL for GitHub Enterprise Server (e.g. `https://github.mycompany.com`) |

### LLM Settings

| Variable | Required | Default | Description |
|---|---|---|---|
| `LLM_PROVIDER` | No | `ollama` | Active provider: `ollama`, `claude`, `openai`, `github_models` |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | No | `llama3` | Ollama model name |
| `ANTHROPIC_API_KEY` | For Claude | — | Anthropic API key |
| `ANTHROPIC_MODEL` | No | — | Claude model override (e.g. `claude-3-5-sonnet-20241022`) |
| `ANTHROPIC_BASE_URL` | No | — | Proxy base URL for Claude (e.g. OpenRouter) |
| `ANTHROPIC_AUTH_TOKEN` | No | — | Alternative auth token for Claude proxy endpoints |
| `OPENAI_API_KEY` | For OpenAI | — | OpenAI API key |
| `GITHUB_MODELS_MODEL` | No | `gpt-5` | GitHub Models model name |
| `GITHUB_MODELS_ENDPOINT` | No | `https://models.inference.ai.azure.com` | GitHub Models endpoint |

### Cache & Output Settings

| Variable | Required | Default | Description |
|---|---|---|---|
| `CACHE_TTL_MINUTES` | No | `30` | Alert cache lifetime in minutes |
| `OUTPUT_DIR` | No | `./reports` | Directory for exported report files |
| `DEFAULT_OUTPUT_FORMAT` | No | `text` | Default output format: `text`, `pdf`, `html`, `excel` |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## Usage

### Command-Line Reference

```bash
# Default — uses GITHUB_ORG from .env, auto-detects AI provider
python main.py

# Override the target organisation
python main.py --org my-other-org

# Scan a single repository (faster, narrower scope)
python main.py --repo owner/repo-name

# Interactive organisation selection from all accessible organisations
python main.py --list-orgs

# Enable verbose debug logging (HTTP requests, cache events, AI calls)
python main.py --debug

# Combinations
python main.py --org my-org --debug
python main.py --list-orgs --debug

# Show help
python main.py --help
```

### CLI Options

| Flag | Description |
|---|---|
| `--org <name>` | Override `GITHUB_ORG` from `.env` |
| `--repo <owner/repo>` | Restrict analysis to a single repository |
| `--list-orgs` | Fetch all accessible organisations and select interactively |
| `--debug` | Enable verbose logging |
| `--help` | Show help and exit |

### AI Provider Auto-Detection

On startup, AI Git Guard checks which providers are available and reachable:

| Scenario | Behaviour |
|---|---|
| One provider configured and reachable | Auto-connects silently |
| Multiple providers available | Numbered selection menu is shown |
| No provider configured | Setup instructions are printed and the tool exits |

Provider detection logic:

| Provider | Detection Method |
|---|---|
| **Ollama** | HTTP health-check to `OLLAMA_BASE_URL/api/tags` |
| **Claude** | Checks for non-empty `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` |
| **OpenAI** | Checks for `OPENAI_API_KEY` — placeholder values (e.g. `sk-xxxx`) are rejected |
| **GitHub Models** | Available whenever `GITHUB_TOKEN` is present |

### Organisation Selection (`--list-orgs`)

```
Available organisations:
  1. cloudreach        -- We believe cloud platforms must drive transformation...
  2. IN-Information-Security
  3. ATOS
  4. GLB-CES-PublicCloud

Select organisation [1/2/3/...] (1): 2
✓ Selected: IN-Information-Security
```

> If `--org` is also provided, it takes priority and `--list-orgs` is skipped.

### Interactive Terminal

On startup, the terminal:
1. Connects to the configured AI provider
2. Fetches security alerts from GitHub (or loads from cache)
3. Displays the security summary dashboard
4. Opens the prompt with slash-command autocomplete

#### Natural Language Queries

Type any question in plain English — the Intent Router dispatches it automatically:

```
You: What are my top 5 security risks?
You: How many critical Dependabot alerts are open?
You: Which repository has the most vulnerabilities?
You: Are there any exposed AWS credentials?
You: How do I fix the lodash vulnerability?
You: Which repos are most likely to be attacked next?
You: Are my GitHub Actions workflows safe?
You: Generate an executive PDF report
```

#### Slash Commands

| Command | Module | Description |
|---|---|---|
| `/triage` | M1 | Prioritised alert triage |
| `/remediate` | M2 | Fix and upgrade guidance |
| `/risk` | M4 | Risk prediction and scoring |
| `/workflow` | M5 | GitHub Actions workflow security analysis |
| `/narrate` | M6 | Executive security briefing |
| `/report pdf` | Renderer | Export PDF report |
| `/report html` | Renderer | Export HTML dashboard |
| `/report excel` | Renderer | Export Excel workbook |
| `/report weekly` | Renderer | Weekly org report (10-sheet Excel) |
| `/report enterprise` | Renderer | Enterprise multi-org inventory (4-sheet Excel) |
| `/fetch` | — | Force-refresh all alerts from GitHub |
| `/clear` | — | Clear the terminal screen |
| `/help` | — | Display all available commands |
| `/exit` | — | Quit AI Git Guard |

---

## Output Formats & Reports

### Standard Formats

| Format | Command | Description |
|---|---|---|
| Terminal | *(default)* | Colour-coded Rich output with severity panels |
| PDF | `/report pdf` | reportlab-generated executive report |
| HTML | `/report html` | Self-contained HTML dashboard |
| Excel | `/report excel` | Multi-sheet XLSX workbook |

### Weekly Organisation Report (`/report weekly`)

A 10-sheet Excel workbook covering the complete security state of your organisation:

| Sheet | Contents |
|---|---|
| Executive Summary | KPIs, alert counts, compliance score, overall risk level |
| Analysis & Progress | 30-day trend analysis and improvement metrics |
| Top Risks | Top 50 critical and high severity alerts across all categories |
| Repository Health | Per-repository health matrix with risk levels |
| Recommendations | AI-generated, prioritised remediation actions |
| Repository Risk Pivot | Pivot table — repositories × severity counts |
| Dependabot Details | Full listing with GHSA ID, CVE ID, CVSS score, package ecosystem |
| Code Scanning Details | CWE category, rule name, severity, file path and line number |
| Secret Scanning Details | Secret type, current state, push protection status |
| Supply Chain | Repository language, licence, visibility, and supply chain health |

### Enterprise Repository Inventory (`/report enterprise`)

A 4-sheet cross-organisation Excel report. Requires `--list-orgs` at startup.

| Sheet | Contents |
|---|---|
| Executive Summary | Cross-organisation KPIs |
| All Repositories | Full listing with 23 data columns — language, visibility, stars, forks, alert counts |
| Repository Health | Per-repo vulnerability severity breakdown |
| Organization Risk Pivot | Organisations × alert counts and compliance scores |

```bash
# Step 1 — start with --list-orgs so the tool discovers all your organisations
python main.py --list-orgs

# Step 2 — inside the interactive terminal:
You: /report enterprise
```

> The enterprise report fetches data for **all** discovered organisations. This may take several minutes if your token has access to many organisations.

All reports are saved to `./reports/` with a timestamp in the filename.

---

## GitHub Token Permissions

Create a **Fine-Grained Personal Access Token** at:
**GitHub → Settings → Developer Settings → Personal Access Tokens → Fine-Grained Tokens → Generate new token**

| Permission | Scope | Purpose |
|---|---|---|
| `security_events` | Repository | Code Scanning and Secret Scanning alerts |
| `contents` | Repository | Repository metadata and workflow file access |
| `read:org` | Organisation | Organisation-level alert APIs |
| `dependabot_alerts` | Repository | Dependabot vulnerability alerts |

> **Recommendation:** Use Fine-Grained tokens scoped to the specific repositories you need. This follows the principle of least privilege and limits exposure if the token is compromised. Classic tokens are acceptable but grant broader access.

---

## LLM Provider Configuration

### Provider Setup

```env
# Option 1 — Ollama (free, local, private — recommended for sensitive environments)
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3            # alternatives: codellama, mistral, phi3

# Option 2 — Anthropic Claude
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022   # optional — omit to use provider default

# Option 3 — OpenAI GPT
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxxxxxx

# Option 4 — GitHub Models (free tier, uses your existing GITHUB_TOKEN)
LLM_PROVIDER=github_models
GITHUB_MODELS_MODEL=gpt-5
```

### Provider Comparison

| Provider | Cost | Data Privacy | Recommended For |
|---|---|---|---|
| **Ollama** | Free | All data stays on your machine | Getting started; sensitive or air-gapped environments |
| **Claude** | Paid API | Alert data sent to Anthropic | Highest analysis quality and nuance |
| **OpenAI GPT** | Paid API | Alert data sent to OpenAI | Balanced quality and broad availability |
| **GitHub Models** | Free (with token) | Alert data sent to GitHub/Azure | GitHub-native teams wanting cloud quality without separate API keys |

> ⚠️ **Data Privacy:** When using cloud providers (Claude, OpenAI, GitHub Models), your security alert data is transmitted as part of the AI prompt over HTTPS. For repositories containing sensitive or regulated data, use Ollama to keep all data on-premise.

---

## Project Structure

```
ai_git_guard/
│
├── main.py                        # Entry point — delegates to cli/main.py
├── config.py                      # Reads .env; exposes singleton `settings` object
├── models.py                      # Pydantic v2 alert models and enumerations
├── requirements.txt               # Python dependencies
├── .env.example                   # Configuration template
│
├── github/
│   ├── client.py                  # GitHub REST API v3 client (pagination, rate-limit back-off)
│   ├── aggregator.py              # Parses raw JSON into typed models; builds SecuritySummary
│   └── cache.py                   # SQLite-backed response cache with configurable TTL
│
├── llm/
│   ├── base.py                    # LLMAdapter abstract interface + LLMResponse dataclass
│   ├── factory.py                 # Provider selection — returns the correct adapter
│   ├── ollama_adapter.py          # Ollama local inference adapter
│   ├── claude_adapter.py          # Anthropic Claude adapter (supports proxy base URL)
│   ├── openai_adapter.py          # OpenAI GPT adapter
│   └── github_models_adapter.py   # GitHub Models adapter (Azure AI inference)
│
├── modules/
│   ├── base.py                    # BaseModule abstract class
│   ├── router.py                  # IntentRouter — slash-command and LLM-based classification
│   ├── m1_triage.py               # M1: Alert Triage & Prioritization
│   ├── m2_remediation.py          # M2: Code Remediation Generator
│   ├── m3_query.py                # M3: Natural Language Query Engine (with conversation history)
│   ├── m4_risk_prediction.py      # M4: Risk Prediction Engine
│   ├── m5_workflow_analyzer.py    # M5: GitHub Actions Workflow Security Analyzer
│   └── m6_narrator.py             # M6: Executive Security Posture Narrator
│
├── output/
│   ├── renderer.py                # Multi-format renderer: text, PDF, HTML, Excel
│   └── excel_reports.py           # Weekly (10-sheet) and Enterprise (4-sheet) Excel builders
│
├── cli/
│   └── main.py                    # Interactive REPL with prompt_toolkit autocomplete
│
├── reports/                       # Generated report output (gitignored)
└── tests/
    ├── conftest.py
    ├── test_aggregator.py
    ├── test_cache.py
    ├── test_client.py
    ├── test_config.py
    ├── test_factory.py
    ├── test_llm_base.py
    ├── test_models.py
    ├── test_modules.py
    └── test_router.py
```

---

## Running Tests

```bash
# Run the full test suite
pytest

# Run with line-level coverage report
pytest --cov=. --cov-report=term-missing

# Run a specific test file
pytest tests/test_router.py -v
```

---

## Roadmap

| Phase | Status | Scope |
|---|---|---|
| **Phase 1** | ✅ Complete | Interactive terminal · Ollama, Claude, OpenAI, GitHub Models · M1–M6 modules · PDF, HTML, Excel, Weekly, and Enterprise reports |
| **Phase 2** | Planned | Automated PR generation for vulnerability fixes · GitHub Copilot integration · Custom alert filtering and tagging · PR auto-remediation workflows |
| **Phase 3** | Planned | Web UI (Streamlit / FastAPI) · Slack and Teams notifications · Real-time alert monitoring via GitHub webhooks · Role-based access control (RBAC) |

---

## Security Considerations

| Area | Detail |
|---|---|
| **Token storage** | `GITHUB_TOKEN` is stored only in `.env`, which is enforced by `.gitignore`. Treat it as a password — rotate it regularly and use Fine-Grained tokens scoped to the minimum required repositories. |
| **Local AI (Ollama)** | All prompt data remains on your machine. No external network calls are made by the model. Use this option for sensitive or regulated environments. |
| **Cloud AI** | Alert content (CVE descriptions, file paths, secret types) is included in prompts sent over HTTPS to the provider's API. Review your organisation's data-sharing policy before use. |
| **Cache file** | `.alert_cache.db` is created with `0o600` permissions and contains raw alert data. Apply OS-level access controls and include it in your data classification policy. |
| **Generated reports** | Files in `./reports/` may contain CVE details, exposed secret types, and repository metadata. Treat them as confidential documents and restrict access accordingly. |
| **Prompt content** | No adapter sends `GITHUB_TOKEN`, `.env` contents, or any runtime credential to the LLM. Only alert data prepared by each module is included in prompts. |

---

<div align="center">

**AI Git Guard v0.2.0**

*Six AI modules · Four LLM providers · Five output formats · Full organisation and enterprise coverage*

</div>
