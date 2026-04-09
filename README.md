<div align="center">

# 🛡️ AI Git Guard

**AI-Powered GitHub Advanced Security Agent**

*Dependabot · Code Scanning · Secret Scanning — analysed by AI in plain English*

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)]()
[![Version](https://img.shields.io/badge/version-0.2.0-orange.svg)]()

</div>

---

## Overview

**AI Git Guard** is an interactive, AI-powered security assistant that connects to GitHub, reads all your security alerts, and lets you ask questions about them in plain English — just like chatting with a knowledgeable security expert.

> **In plain English:** Imagine having a security analyst sitting next to you. You ask "What are my top 5 risks?" or "How do I fix the lodash issue?" and they instantly read through hundreds of alerts, pick out what matters, and explain it to you in simple language. That's what AI Git Guard does — automatically.

It is designed for **security engineers**, **DevSecOps teams**, and **engineering managers** who need fast, AI-assisted insight into their GitHub security posture — without switching between multiple dashboards.

### What problems does it solve?

| Without AI Git Guard | With AI Git Guard |
|----------------------|-------------------|
| Hundreds of raw security alerts in GitHub dashboards | AI-ranked, prioritised list of "fix these first" |
| You need to know which alert is most dangerous | AI explains severity, exploitability, and business impact |
| Fix instructions are buried in CVE databases | Exact upgrade commands for your package manager |
| Writing security reports takes hours | One command generates an executive PDF or Excel report |
| You need to grep through alert data to answer questions | Just ask in plain English |

---

## Understanding the Core Concepts

> **New to GitHub security?** This section explains the key terms in plain English.

**GitHub Advanced Security (GHAS)** is GitHub's built-in security toolset that automatically scans your code repositories and warns you about three types of problems:

| Alert Type | What it watches for | Plain English Example |
|------------|--------------------|-----------------------|
| **Dependabot Alerts** | Outdated or vulnerable third-party libraries your code depends on | "Your app uses `lodash 4.17.19` which has a known vulnerability. Upgrade to `4.17.21`." |
| **Code Scanning Alerts** | Security flaws and bugs written directly in your source code | "Line 42 in `login.py` is vulnerable to SQL injection — an attacker could dump your database." |
| **Secret Scanning Alerts** | API keys, passwords, or tokens accidentally committed to your code | "An AWS access key was found in `config.js` — it must be revoked immediately." |

**LLM (Large Language Model)** is the AI "brain" (like ChatGPT) that reads your alert data and composes human-readable explanations. AI Git Guard supports several AI providers, including free locally-run options.

---

## Key Features

| Module | ID | What it does | Ask it like… |
|--------|----|-------------|--------------|
| Alert Triage & Prioritization | M1 | Ranks all open alerts by severity, CVE score, and how easily they can be exploited | *"What should I fix first?"* |
| Code Remediation Generator | M2 | Gives exact upgrade commands and patch guidance for every vulnerability | *"How do I fix the lodash issue?"* |
| Natural Language Query Engine | M3 | Answers any free-form question about your alerts in plain English | *"How many critical alerts does repo X have?"* |
| Risk Prediction Engine | M4 | Analyses patterns to predict which repositories are most likely to be attacked next | *"Which repos are at highest risk?"* |
| Workflow Security Analyzer | M5 | Reviews your GitHub Actions CI/CD pipeline YAML files for security misconfigurations | *"Are my workflows safe?"* |
| Security Posture Narrator | M6 | Writes an executive briefing suitable for a CISO or management audience | *"Generate a board-level security summary"* |

**Output formats:** Plain text · PDF · HTML · Excel (XLSX) · Weekly Org Report (XLSX) · Enterprise Inventory (XLSX)

**LLM providers:** Ollama (local, free, private) · Claude (Anthropic) · OpenAI GPT · GitHub Models

---

## How It Works — The Data Pipeline

> **In plain English:** AI Git Guard acts like a relay race. GitHub passes the baton (your alert data) to a local cache, which passes it to a parser, which passes it to the AI, which hands you the final answer. Each step adds value.

The diagram below shows exactly how alert data flows from GitHub's servers to your screen:

### Data Flow

```
┌───────────────────────────────────┐
│         GitHub REST API v3        │
│  (github.com or GitHub Enterprise)│
└──────────────┬────────────────────┘
               │  Secure HTTPS request using your token
               │  Fetches 100 alerts per page, follows
               │  pages automatically until done
               │  Backs off & retries if rate-limited
               ▼
┌───────────────────────────────────┐
│       github/client.py            │
│  GitHubClient — the fetcher       │
│  Retrieves 3 alert categories:    │
│   • Dependabot (library vulns)    │
│   • Code Scanning (code flaws)    │
│   • Secret Scanning (leaked keys) │
└──────────────┬────────────────────┘
               │  Raw alert data (JSON)
               ▼
┌───────────────────────────────────┐
│       github/cache.py             │
│  AlertCache — your local memory   │
│   • Saves data to .alert_cache.db │
│   • Reuses it for up to 30 min    │
│   • Avoids hammering GitHub API   │
└──────────────┬────────────────────┘
               │  Cached or freshly fetched data
               ▼
┌───────────────────────────────────┐
│       github/aggregator.py        │
│  Parses & structures the raw data │
│  into clean, typed objects and    │
│  computes org-wide statistics     │
└──────────────┬────────────────────┘
               │  Clean, structured alert objects
               ▼
┌───────────────────────────────────┐
│      AI Analysis Modules (M1–M6)  │
│  Triage · Remediation · Query     │
│  Risk Prediction · Workflow · Narrate │
│  (alert data is sent to AI prompt)│
└──────────────┬────────────────────┘
               │  AI-generated analysis in plain English
               ▼
┌───────────────────────────────────┐
│      output/renderer.py           │
│  text · PDF · HTML · Excel        │
│  Saved to ./reports/              │
└───────────────────────────────────┘
```

### Step-by-step breakdown

1. **Authentication** — The tool uses your personal `GITHUB_TOKEN` (stored safely in `.env`) to prove its identity to GitHub. GitHub then allows it to read your security alert data via its secure REST API.

2. **Fetching** — Three categories of alerts are fetched: **Dependabot** (vulnerable dependencies), **Code Scanning** (code flaws), and **Secret Scanning** (exposed credentials). GitHub delivers the data in pages of 100 items — the tool follows each page automatically until all alerts are collected.

3. **Rate-limit handling** — GitHub limits how many API requests any tool can make per hour. If that limit is hit (HTTP 429 or 403 response), the tool reads the `X-RateLimit-Reset` header (which tells it exactly when the limit resets), waits, then retries automatically — no action required from you.

4. **Caching** — To avoid fetching the same data repeatedly, the tool stores results in a local SQLite database file (`.alert_cache.db`). On every subsequent query within 30 minutes, the cached copy is used instead of hitting GitHub again. This makes follow-up questions near-instant.

5. **Parsing** — Raw JSON data from GitHub is converted into clean, typed data structures (`DependabotAlert`, `CodeScanningAlert`, `SecretScanningAlert`) using Pydantic's validation. An organisation-wide `SecuritySummary` is also computed (total counts, severity breakdown, compliance score).

6. **AI analysis** — The structured alert data is formatted into an AI prompt and sent to your chosen LLM (Ollama, Claude, OpenAI, or GitHub Models). The AI's **Intent Router** first classifies what you are asking (triage? fix guidance? general question?) and dispatches it to the right module (M1–M6).

7. **Output** — The AI's response is displayed in the terminal as styled, colour-coded text, or exported to `./reports/` as PDF, HTML, or Excel.

---

## AI Architecture — How the Intelligence Works

> **In plain English:** Think of AI Git Guard as a team of specialists, each with a defined job. When you type something, a "receptionist" (the Intent Router) first reads your message and decides which specialist to hand it to. That specialist prepares a detailed briefing from your alert data and asks the AI to write the answer. The AI never has direct access to GitHub — it only reads the structured summary the specialist prepares.

### The AI Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        YOU (the user)                                   │
│  "What should I fix first?" / "/triage" / "Generate a PDF report"       │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │  Your text input
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STEP 1 — Intent Router  (router.py)                  │
│                                                                         │
│  Slash command?  ──YES──▶  Instant mapping (no AI call needed)          │
│       │                    /triage → TRIAGE                             │
│       │                    /risk   → RISK_PREDICTION                    │
│       NO                   /report → REPORT  ... etc.                   │
│       │                                                                 │
│       ▼                                                                 │
│  Natural language? ──▶  LLM Call #1 (classification only, max 20 tokens)│
│                          System: "Classify into one of 10 categories"   │
│                          Returns: "triage" / "query" / "remediation"    │
│                          etc.  (single word, very fast)                 │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │  Intent (enum) + args
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STEP 2 — Module Dispatch  (cli/main.py)              │
│                                                                         │
│   TRIAGE      ──▶  M1 RiskTriageModule                                  │
│   REMEDIATION ──▶  M2 RemediationModule                                 │
│   QUERY       ──▶  M3 NLQueryModule  (with conversation history)        │
│   RISK        ──▶  M4 RiskPredictionModule                              │
│   WORKFLOW    ──▶  M5 WorkflowAnalyzerModule                            │
│   NARRATE     ──▶  M6 NarratorModule                                    │
│   REPORT      ──▶  Choose M1/M2/M6 based on report type, then render   │
│   FETCH       ──▶  Reload GitHub alerts (no AI call)                   │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │  Module receives alert context dict
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STEP 3 — Module Builds AI Prompt                     │
│                                                                         │
│  Each module constructs a detailed prompt containing:                   │
│   • A system instruction  (who the AI should act as)                   │
│   • Your alert data       (Dependabot, Code Scanning, Secret Scanning)  │
│   • Conversation history  (M3 only — last 10 exchanges)                │
│   • Your specific query   (what you asked)                              │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │  Structured prompt
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STEP 4 — LLM Adapter  (llm/)                         │
│                                                                         │
│  LLMAdapter (abstract interface)                                        │
│       │                                                                 │
│       ├── OllamaAdapter       → local server at localhost:11434         │
│       ├── ClaudeAdapter       → Anthropic API (or OpenRouter proxy)     │
│       ├── OpenAIAdapter       → OpenAI GPT API                         │
│       └── GitHubModelsAdapter → Azure AI inference via GITHUB_TOKEN     │
│                                                                         │
│  All adapters return the same LLMResponse object:                      │
│   { text, model, provider, prompt_tokens, completion_tokens }           │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │  LLMResponse.text (the AI's answer)
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STEP 5 — Output Renderer  (output/)                  │
│                                                                         │
│  Terminal (Rich panels, colour-coded by severity)                       │
│  PDF       → reportlab library                                          │
│  HTML      → weasyprint library                                         │
│  Excel     → openpyxl library (10-sheet weekly / 4-sheet enterprise)    │
└─────────────────────────────────────────────────────────────────────────┘
```

### How Many AI Calls Happen Per Question?

> Every time you ask a question, the tool makes at most **2 AI calls** — one to understand what you want, and one to generate the answer.

| Scenario | AI calls | Details |
|----------|----------|---------|
| You type a **slash command** (e.g. `/triage`) | **1 call** | No classification needed — module is known. 1 call to generate analysis. |
| You type **natural language** (e.g. "What should I fix?") | **2 calls** | Call 1: classify intent (≤20 tokens, very fast). Call 2: generate full analysis. |
| You use `/fetch` or `/help` | **0 calls** | These are purely local operations — no AI involved. |

### The Intent Router — AI Reading Your Mind

The `IntentRouter` is the brain's front door. It decides, from your free-form text, which specialist module to invoke. Here is exactly how it works:

```
You type: "Which repos are most vulnerable to attack?"
                    │
                    ▼
  Router sends this to the LLM:
  ┌─────────────────────────────────────────────────────┐
  │ SYSTEM: "You are an intent classifier. Classify     │
  │          into one of: triage, remediation, risk,    │
  │          workflow, narrate, query, report, fetch,   │
  │          help, exit. Reply with ONLY the word."     │
  │                                                     │
  │ USER:   "Which repos are most vulnerable to attack?"│
  └─────────────────────────────────────────────────────┘
                    │
                    ▼
  LLM replies:  "risk"   (a single word, very fast)
                    │
                    ▼
  Router maps "risk" → Intent.RISK_PREDICTION
  Dispatches to M4 RiskPredictionModule
```

If classification fails for any reason, the router safely defaults to the **Query module (M3)** so your question always gets answered.

### System Prompts — Giving the AI its Persona

Each module gives the AI a specific expert identity via a **system prompt**. This is why answers are focused and professional:

| Module | AI Persona (System Prompt role) |
|--------|---------------------------------|
| **M1 Triage** | "You are a senior security engineer expert in GitHub Advanced Security" |
| **M2 Remediation** | "You specialise in dependency management and secure software supply chains" |
| **M3 Query** | "You are AI Git Guard, an expert GitHub Advanced Security analyst assistant" |
| **M4 Risk Prediction** | "You are a senior security risk analyst specialising in predictive threat modelling" |
| **M5 Workflow Analyzer** | "You are a senior DevSecOps engineer and GitHub Actions security expert" |
| **M6 Narrator** | "You are a security communications expert writing briefings for CISOs" |

### Conversation Memory (M3 Query)

The Natural Language Query module (M3) remembers your conversation. It keeps the last **10 exchanges** (question + answer pairs) and includes them in every subsequent prompt, so you can ask follow-up questions naturally:

```
You: How many critical alerts are there?
AI:  There are 12 critical alerts across 5 repositories...

You: Which ones are easiest to fix?        ← follow-up; AI knows "ones" = critical alerts
AI:  Of the 12 critical alerts, the 3 easiest to fix are...

You: Show me just the npm ones.            ← AI remembers the context
AI:  Of those 3, 2 are npm packages...
```

Other modules (M1, M2, M4, M5, M6) are stateless — each invocation is independent.

### The Alert Context Dictionary

Every module receives the same structured data "package" (the **context dict**) containing all your alert objects:

```python
{
  "org":            "my-org-name",
  "repo":           None,                     # or "owner/repo" if --repo was used
  "dependabot":     [DependabotAlert, ...],    # typed Pydantic objects
  "code_scanning":  [CodeScanningAlert, ...],
  "secret_scanning":[SecretScanningAlert, ...],
  "summary":        SecuritySummary,           # org-wide KPI rollup
}
```

Each module serialises only the data it needs into the AI prompt. No module sends your raw GitHub token or `.env` secrets to the AI.

---

## Data Storage & Cache Lifetime

> **In plain English:** The first time you run the tool it downloads all your alerts from GitHub. After that, for the next 30 minutes, it uses the saved copy on your computer instead of re-downloading everything — making your follow-up questions instant. After 30 minutes, it automatically refreshes.

### Where is data stored?

| Artefact | Location | Contents |
|----------|----------|----------|
| **Alert cache** | `ai_git_guard/.alert_cache.db` | Local copy of GitHub alert data (SQLite database file) |
| **Generated reports** | `ai_git_guard/reports/` | Exported PDF, HTML, and Excel report files |
| **Configuration** | `ai_git_guard/.env` | Your tokens and settings — **never committed to Git** |

The cache database (`.alert_cache.db`) is a lightweight SQLite file with a single `cache` table:

| Column | Type | Description |
|--------|------|-------------|
| `key` | TEXT | Identifies what was cached (e.g. `dep:my-org:None:open` = Dependabot alerts, org-wide, open state) |
| `value` | TEXT | The full JSON response from GitHub |
| `stored` | REAL | Unix timestamp recording when the data was saved |

### How long does cached data last? (TTL)

TTL stands for **Time To Live** — it is simply the maximum age allowed for cached data before the tool fetches fresh data from GitHub.

| Setting | Default | Where to change it |
|---------|---------|----------|
| `CACHE_TTL_MINUTES` | **30 minutes** | `.env` file or `config.py` |

**What this means in practice:**
- **Within 30 minutes:** All your questions use the same snapshot of alerts — fast, no API calls.
- **After 30 minutes:** The next query automatically discards the stale cache and fetches fresh data from GitHub.
- **Force refresh anytime:** Type `/fetch` in the terminal to get the latest data immediately, regardless of TTL.

**To change the cache duration**, add or update `CACHE_TTL_MINUTES` in your `.env` file:

```env
CACHE_TTL_MINUTES=15     # Refresh every 15 minutes (good for active incident response)
CACHE_TTL_MINUTES=60     # Refresh every hour (normal day-to-day use)
CACHE_TTL_MINUTES=1440   # Keep for 24 hours (offline/demo use)
```

### Cache lifecycle at a glance

```
You ask a question
       │
       ▼
  ┌─────────────────────┐     YES    ┌────────────────────────┐
  │ Is cached data         │──────────▶│ Use saved data — fast,  │
  │ fresh (< TTL)?         │           │ no GitHub API call      │
  └─────────────────────┘           └────────────────────────┘
       │ NO (or /fetch used)
       ▼
  ┌─────────────────────┐           ┌────────────────────────┐
  │ Fetch fresh data       │──────────▶│ Save it to cache with   │
  │ from GitHub API        │           │ current timestamp       │
  └─────────────────────┘           └────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Python 3.10 or newer ([download here](https://www.python.org/downloads/))
- A GitHub account with a Personal Access Token (PAT) — see [GitHub Token Permissions](#github-token-permissions)
- At least one AI provider configured (Ollama is free and runs locally — recommended for getting started)

### 1. Clone & install

```bash
git clone https://github.com/your-org/ai-git-guard.git
cd ai-git-guard

# Create an isolated Python environment (keeps dependencies separate from your system)
python -m venv .venv

# Activate it:
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\activate             # Windows (PowerShell)

# Install all required packages
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Open .env in any text editor and fill in your values
```

**Minimum required settings in `.env`:**
```env
GITHUB_TOKEN=ghp_your_token_here   # Your GitHub Personal Access Token
GITHUB_ORG=your-org-name           # The GitHub organisation to scan
LLM_PROVIDER=ollama                # AI brain to use (ollama = free & local)
OLLAMA_MODEL=llama3                # The Ollama model to run
```

### 3. Install Ollama (free local AI — recommended)

> **Why Ollama?** It runs the AI entirely on your own computer — no API costs, no data sent to the cloud. Perfect for getting started and for sensitive environments.

```bash
# macOS / Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows — download the installer from https://ollama.ai/download

# Then pull a model (this downloads the AI "brain" to your machine)
ollama pull llama3          # ~4GB download, fast & general purpose
# OR
ollama pull codellama:13b   # Better for code analysis (needs 16GB+ RAM)
```

Once installed, Ollama runs as a background service at `http://localhost:11434`. AI Git Guard will detect it automatically.

---

## Usage

### Command-Line Reference

All commands start with `python main.py`. You can customise which organisation or repository to analyse using optional flags:

```bash
# Default — uses the org from .env, auto-detects your AI provider
python main.py

# Scan a different GitHub organisation (overrides .env setting)
python main.py --org my-other-org

# Scan a single repository only (faster, narrower scope)
python main.py --repo my-org/my-repo

# Browse and pick from ALL organisations your token can access
python main.py --list-orgs

# Enable verbose debug logging (see every HTTP request and cache event)
python main.py --debug

# Combine flags
python main.py --list-orgs --debug
python main.py --org my-org --repo my-org/my-repo --debug

# Show help
python main.py --help
```

### CLI Options Summary

| Flag | Description |
|------|-------------|
| `--org <name>` | Override the GitHub organisation from `.env` |
| `--repo <owner/repo>` | Scan a single repository instead of the full organisation |
| `--list-orgs` | Fetch all organisations your token can access and choose interactively |
| `--debug` | Enable verbose logging — shows HTTP requests, cache hits, AI calls, etc. |
| `--help` | Show CLI help and exit |

### AI Provider Auto-Detection

When you run `python main.py`, the tool automatically checks which AI providers you have configured and picks one for you:

| Scenario | What happens |
|----------|-----------|
| **1 provider** has valid credentials | Auto-connects — no prompt shown |
| **Multiple providers** have credentials | Shows a numbered menu so you can choose |
| **No providers** configured | Prints setup instructions and exits |

How each provider is detected:

| Provider | How detection works |
|----------|-------------------|
| **Ollama** | Sends a quick health-check ping to `http://localhost:11434` — if it responds, Ollama is running |
| **Claude** | Checks for a non-empty `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` in `.env` |
| **OpenAI** | Checks for a valid `OPENAI_API_KEY` (a placeholder value like `sk-xxxx` is ignored) |
| **GitHub Models** | Detects automatically when `GITHUB_TOKEN` is present — uses GitHub's free AI marketplace |

### Organisation Selection (`--list-orgs`)

When launched with `--list-orgs`, the tool fetches every organisation your GitHub token can access and shows them as a numbered list:

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

### Starting the Interactive Terminal

```bash
python main.py
```

This opens the interactive AI terminal. On startup it:
1. Auto-detects and connects to your AI provider (Ollama, Claude, OpenAI, or GitHub Models)
2. Fetches all security alerts from GitHub (or loads them from the local cache)
3. Displays your **security summary dashboard** — total alerts by type and severity
4. Waits for your questions or slash commands

### Asking Questions in Plain English

You can type any question and the AI will route it to the right module automatically:

```
You: What are my top 5 security risks?
You: How many critical Dependabot alerts are open?
You: Which repository has the most vulnerabilities?
You: Are there any exposed AWS keys or secrets?
You: How do I fix the lodash vulnerability?
You: Give me a prioritised triage of all alerts
You: Which repos are most likely to be attacked next?
You: Are my GitHub Actions workflows safe?
You: Generate a PDF executive report
```

You never need to know which module handles the question — the AI Intent Router classifies your input and dispatches it to the right specialist module (M1–M6) automatically.

### Interactive Commands (Slash Commands)

For power users, slash commands provide instant access to specific features without AI routing overhead:

| Command | What it does |
|---------|--------|
| *Any plain English question* | AI auto-routes to the right module |
| `/triage` | Run full alert triage and prioritization (M1) |
| `/remediate` | Get fix and upgrade commands for vulnerabilities (M2) |
| `/risk` | AI-powered risk prediction — which repos are most at risk (M4) |
| `/workflow` | Analyse GitHub Actions workflow files for security issues (M5) |
| `/narrate` | Generate an executive security briefing (M6) |
| `/report pdf` | Export report as a PDF file |
| `/report html` | Export report as an HTML dashboard |
| `/report excel` | Export report as an Excel workbook |
| `/report weekly` | Generate the Weekly Organisation security report (Excel, 10 sheets) |
| `/report enterprise` | Generate Enterprise multi-org repository inventory (Excel, requires `--list-orgs`) |
| `/fetch` | Force-refresh all alerts from GitHub right now (bypasses cache) |
| `/clear` | Clear the terminal screen |
| `/help` | Show all available commands |
| `/exit` | Quit AI Git Guard |

---

### Weekly Organisation Report (`/report weekly`)

> **What is it?** A comprehensive 10-sheet Excel workbook covering every security dimension of your entire organisation — suitable for weekly security reviews and board reporting.

Generates a professionally formatted Excel report with 10 sheets:

| Sheet | Contents |
|-------|----------|
| **Executive Summary** | KPIs, total alert counts, overall compliance score, and risk level |
| **Analysis & Progress** | 30-day trend analysis and improvement metrics |
| **Top Risks** | Top 50 critical and high severity alerts across all alert categories |
| **Repository Health** | Per-repository health matrix showing alert counts and risk levels |
| **Recommendations** | AI-generated, prioritised remediation actions |
| **Repository Risk Pivot** | Pivot table — repositories vs. severity counts (great for spotting patterns) |
| **Dependabot Details** | Full Dependabot alert listing with CVE ID, CVSS score, and package ecosystem |
| **Code Scanning Details** | Code scanning alerts with CWE category, rule name, severity, and file location |
| **Secret Scanning Details** | Exposed secrets with type, current state, and push protection status |
| **Supply Chain** | Repository-level supply chain health (language, licence, visibility) |

```
You: /report weekly
```

### Enterprise Repository Inventory (`/report enterprise`)

> **What is it?** A multi-organisation Excel report that gives a bird's-eye view of all repositories and their security health across every organisation your token can access. Ideal for group-level security reviews.

**Requires `--list-orgs`** at startup (so the tool knows which organisations to include).

| Sheet | Contents |
|-------|----------|
| **Executive Summary** | Cross-organisation KPIs — total repos, alert breakdowns, risk scores |
| **All Repositories** | Full repository listing (23 data columns) — language, visibility, stars, forks, alert counts |
| **Repository Health** | Per-repo health matrix with vulnerability severity breakdown |
| **Organization Risk Pivot** | Pivot table — organisations × total repos, alerts, and compliance scores |

```bash
# Step 1 — start with --list-orgs so the tool discovers all your organisations
python main.py --list-orgs

# Step 2 — inside the interactive terminal:
You: /report enterprise
```

> **Note:** The enterprise report fetches repository and alert data for **all** discovered organisations, which may take a few minutes if your token has access to many organisations.

---

## GitHub Token Permissions

> **What is a GitHub Token?** It's like a password that lets AI Git Guard read your security alerts on your behalf — without giving away your actual GitHub login credentials. You create it once in your GitHub settings and paste it into `.env`.

Create a **Fine-Grained Personal Access Token** at:
**GitHub → Settings → Developer Settings → Personal Access Tokens → Fine-Grained Tokens → Generate new token**

Required permissions (grant read-only access to each):

| Permission | Scope | Required For |
|-----------|------|-------------|
| `security_events` | Repository | Code Scanning + Secret Scanning alerts |
| `contents` | Repository | Repository metadata and file access |
| `read:org` | Organization | Organisation-level alert APIs |
| `dependabot_alerts` | Repository | Dependabot vulnerability alerts |

> **Security tip:** Fine-Grained Tokens let you restrict which specific repositories the token can access. Prefer these over classic tokens for minimum required access.

---

## LLM Provider Configuration

> **Which AI provider should I choose?** If you are getting started or working with sensitive data, use **Ollama** — it's free, runs on your machine, and never sends data to the internet. Use **Claude** or **OpenAI** for higher-quality analysis, but be aware that your alert data will be sent to their cloud servers.

Switch AI provider by changing one line in `.env`:

```env
# ── Option 1: Ollama (free, local, private — recommended) ──────────────────
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3          # or: codellama, mistral, phi3

# ── Option 2: Anthropic Claude (highest quality analysis) ──────────────────
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx

# ── Option 3: OpenAI GPT ───────────────────────────────────────────────────
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxxxxxx

# ── Option 4: GitHub Models (free with your GitHub token) ──────────────────
LLM_PROVIDER=github_models
GITHUB_MODELS_MODEL=gpt-4o   # Select from GitHub's AI Marketplace
# GITHUB_TOKEN is already required — no separate key needed
```

### AI Provider Comparison

| Provider | Cost | Privacy | Best for |
|----------|------|---------|----------|
| **Ollama** | Free | All data stays on your machine | Getting started, sensitive environments, air-gapped systems |
| **Claude** | Paid API | Alert data sent to Anthropic | Highest quality, most nuanced analysis |
| **OpenAI GPT** | Paid API | Alert data sent to OpenAI | Balanced quality and availability |
| **GitHub Models** | Free (with token) | Alert data sent to GitHub/Azure | GitHub-native users who want cloud quality without extra API keys |

> **⚠️ Data Privacy Warning:** Cloud providers (Claude, OpenAI, GitHub Models) receive your alert data as part of the AI prompt. Always use **Ollama** for sensitive repositories or environments where data must not leave your network.

---

## Project Structure

> **How the codebase is organised:** Each folder has a clear, specific job. You don't need to understand all of it to use the tool — but this helps if you want to extend or debug it.

```
ai_git_guard/
│
├── main.py                    # Start here — launches the interactive terminal
├── config.py                  # Reads .env settings and detects available AI providers
├── models.py                  # Data shapes for alerts (Dependabot, Code Scanning, Secret Scanning)
├── requirements.txt           # Python packages to install
├── .env.example               # Template — copy to .env and fill in your values
│
├── github/                    # Everything to do with talking to GitHub
│   ├── client.py              # Makes authenticated API calls (handling pagination & rate limits)
│   ├── aggregator.py          # Converts raw GitHub JSON into clean, typed Python objects
│   └── cache.py               # Saves API responses locally to avoid repeat downloads
│
├── llm/                       # Everything to do with AI providers
│   ├── base.py                # Common interface all AI adapters must follow
│   ├── factory.py             # Picks the right AI adapter based on your config
│   ├── ollama_adapter.py      # Connects to a local Ollama instance
│   ├── claude_adapter.py      # Connects to Anthropic Claude API
│   ├── openai_adapter.py      # Connects to OpenAI GPT API
│   └── github_models_adapter.py # Connects to GitHub's AI Marketplace (Azure AI inference)
│
├── modules/                   # The six AI analysis specialist modules
│   ├── base.py                # Common interface all modules must follow
│   ├── router.py              # Intent Router — reads your input and picks the right module
│   ├── m1_triage.py           # M1: Alert Triage & Prioritization
│   ├── m2_remediation.py      # M2: Code Remediation Generator (fix commands per CVE)
│   ├── m3_query.py            # M3: Natural Language Q&A Engine (with conversation history)
│   ├── m4_risk_prediction.py  # M4: AI Risk Prediction (pattern-based proactive risk scoring)
│   ├── m5_workflow_analyzer.py# M5: GitHub Actions Workflow Security Analyzer
│   └── m6_narrator.py         # M6: Executive Security Briefing Narrator
│
├── output/                    # Report generation
│   ├── renderer.py            # Converts AI output to text / PDF / HTML / Excel
│   └── excel_reports.py       # Builds the Weekly Org and Enterprise Excel reports
│
├── cli/
│   └── main.py                # The interactive terminal loop with slash-command autocomplete
│
├── reports/                   # Where exported report files are saved (gitignored)
└── tests/
    ├── test_aggregator.py
    └── test_cache.py
```

---

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage report (shows which lines of code are tested)
pytest --cov=. --cov-report=term-missing
```

---

## Roadmap

| Phase | Status | Scope |
|-------|--------|-------|
| **Phase 1** | ✅ Current | Interactive terminal · Local Ollama LLM · M1 Triage · M2 Remediation · M3 Natural Language Query · M4 Risk Prediction · M5 Workflow Analyzer · M6 Narrator · 4 AI providers · PDF / HTML / Excel / Weekly / Enterprise reports |
| **Phase 2** | Planned | Auto-PR generation for vulnerability fixes · Copilot integration · Custom alert tagging and filtering · PR auto-remediation |
| **Phase 3** | Planned | Web GUI (Streamlit / FastAPI) · Slack / Teams notifications · Real-time alert monitoring via GitHub webhooks · RBAC (role-based access control) |

---

## Security Considerations

| Area | Details |
|------|---------|
| **Token storage** | `GITHUB_TOKEN` lives only in `.env` — never committed to Git (`.gitignore` enforced). Treat it like a password. |
| **Local AI (Ollama)** | All alert data stays on your machine — nothing is transmitted to external services. Recommended for sensitive environments. |
| **Cloud AI (Claude, OpenAI, GitHub Models)** | Alert data is included in the prompt and sent to the provider's cloud servers over HTTPS. Review your organisation's data-sharing policy before using these providers with sensitive repositories. |
| **Cache file on disk** | `.alert_cache.db` is a local SQLite file containing raw alert data. Apply OS-level file permissions to protect it from unauthorised access. |
| **Generated reports** | Files in `./reports/` may contain sensitive CVE details and secret type names — treat them as confidential documents. |

---

<div align="center">

**AI Git Guard v0.2.0** — GitHub Advanced Security Interactive AI Terminal

*Six AI modules · Four LLM providers · Five output formats · Full organisation coverage*

</div>
