# AI Git Guard — Improvement Plan

**Version Reviewed:** 0.2.0 (Phase 1)
**Review Date:** 2 April 2026
**Reviewer:** Senior AI & Python Expert

---

## Executive Summary

AI Git Guard is a well-architected, modular AI-powered GitHub security assistant. The adapter pattern for LLM providers, Pydantic data models, and intent-routing pipeline are solid foundations. However, based on a thorough review of the entire codebase (~4,500 LOC across 30+ files), the README, and the planning document, there are **42 actionable improvements** across 8 categories that would harden the tool for production use, improve maintainability, and close security/reliability gaps.

**Priority breakdown:** 8 Critical | 12 High | 14 Medium | 8 Low

---

## Table of Contents

1. [Critical Bugs](#1-critical-bugs)
2. [Security Hardening](#2-security-hardening)
3. [Code Quality & Maintainability](#3-code-quality--maintainability)
4. [Error Handling & Resilience](#4-error-handling--resilience)
5. [Testing](#5-testing)
6. [Performance](#6-performance)
7. [Architecture & Design](#7-architecture--design)
8. [Missing Features & Enhancements](#8-missing-features--enhancements)

---

## 1. Critical Bugs

| # | Issue | File | Severity | Description |
|---|-------|------|----------|-------------|
| 1.1 | **Rate-limit handler sleeps but never retries** | `github/client.py` | **Critical** | `_handle_rate_limit()` calls `time.sleep(wait)` then raises `RateLimitExceeded`. The caller `_request()` does not catch or retry. The sleep is wasted — the request fails anyway. The `_request()` method should wrap the call in a retry loop that re-attempts after the sleep. |
| 1.2 | **`datetime.utcnow()` is deprecated** | `models.py`, `modules/m4_risk_prediction.py`, `modules/m6_narrator.py`, `output/renderer.py` | **Medium** | Python 3.12+ deprecates `datetime.utcnow()` (returns naive datetime). Replace with `datetime.now(timezone.utc)` across all files. |
| 1.3 | **`Settings` uses class-level attributes** | `config.py` | **Medium** | All settings are evaluated once at class definition time via `os.getenv()`. They are shared across all instances. If `.env` changes at runtime or tests monkeypatch `os.environ`, the settings won't reflect updates. Migrate to `__init__`-based initialization or use `pydantic-settings`. |
| 1.4 | **`CACHE_TTL_MINUTES` crashes on bad input** | `config.py:39` | **Medium** | `int(os.getenv("CACHE_TTL_MINUTES", "30"))` raises `ValueError` if the env var contains a non-numeric string (e.g., `"thirty"`). Wrap in try/except with a sensible default. |

### Recommended Fixes

**1.1 — Rate-limit retry in `_request()`:**

```python
def _request(self, path: str, params: Optional[dict] = None) -> httpx.Response:
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            response = self._client.get(path, params=params)
        except httpx.ConnectError as exc:
            raise GitHubNetworkError(...) from exc
        # ... other network error handling ...

        if response.status_code in (403, 429) and attempt < max_retries:
            self._handle_rate_limit(response)  # sleep only, don't raise
            continue  # retry the request
        elif response.status_code in (403, 429):
            raise RateLimitExceeded(response.status_code, "Rate limit exceeded after retries")

        # ... rest of success/error handling ...
        return response
```

**1.2 — datetime fix:**

```python
# Before
from datetime import datetime
generated_at: datetime = Field(default_factory=datetime.utcnow)

# After
from datetime import datetime, timezone
generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

---

## 2. Security Hardening

| # | Issue | File | Severity | Description |
|---|-------|------|----------|-------------|
| 2.1 | **Incomplete HTML escaping** | `output/renderer.py` | **High** | `_safe_html()` escapes `&`, `<`, `>` but not quotes (`"`, `'`). While alert severity values come from controlled enums, other fields like `org_name`, repository names, or rule descriptions could contain quotes. Use Python's built-in `html.escape()` instead. |
| 2.2 | **LLM output rendered as HTML without sanitisation** | `output/renderer.py` | **High** | AI-generated text is converted to HTML via `_content_to_html()` and rendered in reports. A compromised or hallucinating LLM could produce `<script>` tags or other HTML payloads. Sanitise LLM output before HTML rendering. |
| 2.3 | **Token scope not validated** | `github/client.py` | **Medium** | `validate_token()` only checks if `/user` succeeds. It does not verify the token has the required scopes (`security_events`, `read:org`, `dependabot_alerts`). Add a `/user` response header check for `X-OAuth-Scopes`. |
| 2.4 | **Fragile API key placeholder check** | `config.py:68` | **Low** | OpenAI detection checks `OPENAI_API_KEY != "sk-xxxx"`. Users with different placeholder values (e.g., `"sk-YOUR_KEY_HERE"`) will pass. Check for a minimum key length or valid prefix pattern instead. |
| 2.5 | **Cache file permissions** | `github/cache.py` | **Low** | `.alert_cache.db` stores raw alert data including CVE details and secret type names. On shared systems, apply restrictive file permissions (e.g., `0o600`) when creating the database file. |

### Recommended Fixes

**2.1 — Replace custom escaping:**

```python
# Before
def _safe_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# After
import html
def _safe_html(text: str) -> str:
    return html.escape(text, quote=True)
```

**2.2 — Sanitise LLM output for HTML:**

```python
import re
def _sanitise_html(text: str) -> str:
    """Strip dangerous HTML tags from LLM output."""
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<(iframe|object|embed|form|input|link|meta|style)[^>]*>.*?</\1>',
                  '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)
    return text
```

**2.3 — Token scope validation:**

```python
def validate_token(self) -> dict:
    response = self._request("/user")
    user_data = response.json()
    scopes = response.headers.get("X-OAuth-Scopes", "")
    required = {"security_events", "read:org"}
    missing = required - set(s.strip() for s in scopes.split(","))
    if missing:
        logger.warning("Token missing scopes: %s", ", ".join(missing))
    return user_data
```

---

## 3. Code Quality & Maintainability

| # | Issue | File | Severity | Description |
|---|-------|------|----------|-------------|
| 3.1 | **Unused dependencies in requirements.txt** | `requirements.txt` | **High** | 4 packages are installed but never imported: `PyGithub` (httpx is used instead), `Jinja2` (prompts are hardcoded strings), `weasyprint` (HTML rendering not implemented), `responses` (tests use `pytest-mock`, not `responses`). Remove or implement their intended features. |
| 3.2 | **Duplicated styling code** | `output/renderer.py`, `output/excel_reports.py` | **Medium** | Colour palettes (`_NAVY`, `_RED`, etc.) and helper functions (`_apply_header_row`, `_apply_data_cell`, `_title_block`, `_set_col_widths`) are duplicated between the two output files. Extract into a shared `output/styles.py` module. |
| 3.3 | **Empty `prompts/` directory** | Project structure | **Medium** | The README lists a `prompts/` directory and Jinja2 is in requirements, but the directory doesn't exist and prompts are hardcoded as string constants in each module. Either externalize prompts into template files or remove the reference and dependency. |
| 3.4 | **Inconsistent enum comparison in M2** | `modules/m2_remediation.py` | **Low** | Uses `a.state.value == "open"` (string comparison) instead of `a.state == AlertState.OPEN` (enum comparison) as used consistently everywhere else. |
| 3.5 | **No `conftest.py` with shared fixtures** | `tests/` | **Medium** | Shared test fixtures (mock GitHub responses, sample alert objects, mock LLM adapter) should be in a `conftest.py` so all test files can reuse them. |
| 3.6 | **Missing `__all__` exports** | All `__init__.py` files | **Low** | Packages don't define `__all__`, which means `from package import *` exposes internals. Define explicit exports. |
| 3.7 | **No type stub for `ollama` SDK** | `llm/ollama_adapter.py` | **Low** | The `ollama` SDK's response is typed as `dict`. The `.get("message", {}).get("content", "")` chain is fragile. Pin and type the response structure. |

### Recommended Action

**3.1 — Dependency cleanup:**

```txt
# REMOVE from requirements.txt (or implement their features):
# PyGithub==2.3.0        → httpx is used directly; remove PyGithub
# Jinja2==3.1.4          → prompts are hardcoded; remove or implement template system
# weasyprint==62.3       → not imported anywhere; remove or implement HTML-to-PDF
# responses==0.25.3      → use respx (httpx-compatible) instead; tests use pytest-mock
```

**3.3 — Externalise prompts (if Jinja2 is kept):**

```
prompts/
├── m1_triage_system.txt
├── m2_remediation_system.txt
├── m3_query_system.txt
├── m4_risk_system.txt
├── m5_workflow_system.txt
├── m6_narrator_system.txt
└── router_system.txt
```

Each module would load its prompt via:
```python
from pathlib import Path
SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "m1_triage_system.txt").read_text()
```

This enables non-developer users to tune prompts without editing Python code — a significant operational advantage.

---

## 4. Error Handling & Resilience

| # | Issue | File | Severity | Description |
|---|-------|------|----------|-------------|
| 4.1 | **No error handling in Ollama adapter** | `llm/ollama_adapter.py` | **Critical** | If Ollama is unreachable, crashed, or the model isn't pulled, the raw `ollama` SDK exception propagates unhandled. Users see a cryptic traceback. Add try/except with a clear error message. |
| 4.2 | **No retry logic in OpenAI adapter** | `llm/openai_adapter.py` | **High** | Unlike the Claude adapter (which retries on 429/502/503), the OpenAI adapter has zero retry logic. OpenAI rate limits will crash the tool. |
| 4.3 | **No retry logic in GitHub Models adapter** | `llm/github_models_adapter.py` | **High** | Same issue as OpenAI — no retry on transient errors. |
| 4.4 | **Silent exception swallowing** | `cli/main.py` | **High** | Enterprise report generation uses `except Exception: pass` blocks when fetching alerts for individual orgs. Failed orgs are silently skipped with no log message. At minimum, log the error. |
| 4.5 | **No corrupt database handling** | `github/cache.py` | **Medium** | If `.alert_cache.db` becomes corrupted (disk full, interrupted write), SQLite raises `sqlite3.DatabaseError`. The tool crashes. Add a fallback that deletes and recreates the cache. |
| 4.6 | **Partial fetch failure not handled** | `cli/main.py` | **Medium** | `_load_context()` fetches Dependabot, Code Scanning, and Secret Scanning sequentially. If code scanning fails (e.g., not enabled on the org), the entire context load fails. Should handle each type independently and proceed with partial data. |

### Recommended Fixes

**4.1 — Ollama error handling:**

```python
def complete(self, prompt: str, system: Optional[str] = None, max_tokens: int = 2048) -> LLMResponse:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        response = self._client.chat(
            model=self._model,
            messages=messages,
            options={"num_predict": max_tokens},
        )
    except Exception as exc:
        raise RuntimeError(
            f"Ollama request failed ({self._base_url}, model={self._model}). "
            f"Ensure Ollama is running and the model is pulled: ollama pull {self._model}\n"
            f"Original error: {exc}"
        ) from exc

    text = response.get("message", {}).get("content", "")
    return LLMResponse(text=text, model=self._model, provider="ollama")
```

**4.2 — Add retry mixin for all adapters:**

Create a shared retry decorator in `llm/base.py`:

```python
import functools, time

def retry_on_transient(max_retries=3, backoff=(2, 5, 10), retryable_codes=(429, 502, 503)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    status = getattr(e, 'status_code', None)
                    if status not in retryable_codes:
                        raise
                    last_err = e
                    wait = backoff[min(attempt, len(backoff) - 1)]
                    logger.warning("Retry %d/%d after %ds: %s", attempt+1, max_retries, wait, e)
                    time.sleep(wait)
            raise last_err
        return wrapper
    return decorator
```

Apply to all adapter `complete()` methods. Remove the duplicate retry logic from `ClaudeAdapter`.

**4.5 — Corrupt cache recovery:**

```python
def __init__(self, db_path, ttl_minutes):
    try:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("SELECT 1 FROM cache LIMIT 1")
    except sqlite3.DatabaseError:
        logger.warning("Cache database corrupted — recreating: %s", db_path)
        db_path.unlink(missing_ok=True)
        self._conn = sqlite3.connect(str(db_path))
    self._create_table()
```

---

## 5. Testing

| # | Issue | Severity | Description |
|---|-------|----------|-------------|
| 5.1 | **Only 2 test files covering 2 of 15+ modules** | **Critical** | Current tests cover only `github/aggregator.py` and `github/cache.py`. No tests exist for the client, LLM adapters, intent router, analysis modules, config, or output rendering. |
| 5.2 | **No integration tests** | **Critical** | No end-to-end tests that mock GitHub API + LLM and exercise the full pipeline. |
| 5.3 | **No CI/CD pipeline** | **High** | No GitHub Actions workflow for automated testing on push/PR. |
| 5.4 | **Wrong mocking library** | **Medium** | `responses` (for `requests` library) is installed, but the project uses `httpx`. Use `respx` instead for httpx mocking. |
| 5.5 | **No `conftest.py`** | **Medium** | Missing shared fixtures for sample alerts, mock LLM, mock GitHub client. |

### Recommended Test Plan

| Component | Priority | Tests Needed | Est. Tests |
|-----------|----------|-------------|------------|
| `github/client.py` | **P0** | Pagination, rate-limit retry, GHE URL, error handling, network errors | 10–12 |
| `modules/router.py` | **P0** | Slash command parsing, LLM classification, fallback to QUERY, edge cases | 8–10 |
| `llm/factory.py` | **P0** | Provider creation, unknown provider, auto-detection | 5–6 |
| `config.py` | **P1** | Validation, env var parsing, provider detection, bad CACHE_TTL | 6–8 |
| `modules/m1_triage.py` | **P1** | Prompt construction, empty alerts, severity sorting | 4–5 |
| `modules/m3_query.py` | **P1** | Conversation history, empty query, context building | 5–6 |
| `modules/m2_remediation.py` | **P1** | Alert filtering, ecosystem detection | 3–4 |
| `modules/m4_risk_prediction.py` | **P2** | Risk scoring, prompt construction | 3–4 |
| `modules/m5_workflow_analyzer.py` | **P2** | Workflow detection, YAML security checks | 3–4 |
| `modules/m6_narrator.py` | **P2** | Narrative generation, summary formatting | 3–4 |
| `output/renderer.py` | **P2** | HTML escaping, template selection, file output | 5–6 |
| `output/excel_reports.py` | **P2** | Sheet creation, data population, styling | 4–5 |
| Integration (end-to-end) | **P0** | Full pipeline with mocked externals | 5–8 |
| **Total** | | | **~70–85 tests** |

### Recommended `conftest.py`:

```python
# tests/conftest.py
import pytest
from models import *

@pytest.fixture
def sample_dependabot_alert():
    return DependabotAlert(
        alert_number=1,
        repository=Repository(id=1, name="test-repo", full_name="org/test-repo"),
        state=AlertState.OPEN,
        package=DependabotPackage(ecosystem="npm", name="lodash"),
        advisory=DependabotSecurityAdvisory(
            ghsa_id="GHSA-xxxx", cve_id="CVE-2021-23337",
            summary="Prototype Pollution", severity=Severity.HIGH, cvss_score=7.2,
        ),
        patched_version="4.17.21",
    )

@pytest.fixture
def mock_llm():
    from llm.base import LLMAdapter, LLMResponse
    class MockLLM(LLMAdapter):
        def __init__(self, response_text="mock response"):
            self._response = response_text
        @property
        def provider_name(self): return "mock"
        def complete(self, prompt, system=None, max_tokens=2048):
            return LLMResponse(text=self._response, model="mock", provider="mock")
    return MockLLM

@pytest.fixture
def sample_context(sample_dependabot_alert):
    from models import SecuritySummary
    return {
        "org": "test-org",
        "repo": None,
        "dependabot": [sample_dependabot_alert],
        "code_scanning": [],
        "secret_scanning": [],
        "summary": SecuritySummary(org="test-org", total_dependabot=1, open_dependabot=1),
    }
```

### Recommended GitHub Actions CI:

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "${{ matrix.python-version }}" }
      - run: pip install -r requirements.txt
      - run: pytest --cov=. --cov-report=xml -v
      - uses: codecov/codecov-action@v4
```

---

## 6. Performance

| # | Issue | File | Severity | Description |
|---|-------|------|----------|-------------|
| 6.1 | **Sequential alert fetching** | `cli/main.py` | **High** | `_load_context()` fetches Dependabot, Code Scanning, and Secret Scanning one after another. These are independent API calls that could run in parallel using `concurrent.futures.ThreadPoolExecutor`, reducing startup time by ~3x. |
| 6.2 | **All paginated results loaded into memory** | `github/client.py` | **Medium** | Every `paginate()` caller wraps it in `list(self.paginate(...))`, materializing all pages into memory at once. For orgs with thousands of alerts, this is wasteful. Consider streaming or chunked processing where possible. |
| 6.3 | **Full alert serialisation on every query** | `modules/m3_query.py` | **Medium** | Every M3 query rebuilds the full alert summary text and conversation history. For orgs with many alerts, this creates very large prompts that may exceed LLM token limits. Add a configurable alert cap (e.g., top 50 by severity) and estimate token count before sending. |
| 6.4 | **Synchronous rate-limit sleep** | `github/client.py` | **Low** | `time.sleep()` blocks the entire process. For a CLI tool this is acceptable, but for future web/API deployment, async sleep would be needed. |
| 6.5 | **No connection pooling configuration** | `github/client.py` | **Low** | `httpx.Client` uses default connection pooling. For high-volume pagination, configuring `limits=httpx.Limits(max_connections=10)` could help. |

### Recommended Fix for 6.1:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def _load_context(gh, org, repo, cache):
    results = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(_fetch_dependabot, gh, org, repo, cache): "dependabot",
            pool.submit(_fetch_code_scanning, gh, org, repo, cache): "code_scanning",
            pool.submit(_fetch_secret_scanning, gh, org, repo, cache): "secret_scanning",
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as exc:
                logger.warning("Failed to fetch %s: %s", key, exc)
                results[key] = []
    return results
```

---

## 7. Architecture & Design

| # | Issue | File | Severity | Description |
|---|-------|------|----------|-------------|
| 7.1 | **God function: `cli()` entry point** | `cli/main.py` | **High** | The `cli()` function is ~350+ lines with deep nesting handling org selection, LLM selection, data fetching, and the interactive loop. Extract into separate functions: `select_org()`, `select_llm()`, `load_data()`, `interactive_loop()`. |
| 7.2 | **Tight coupling to `settings` singleton** | All modules | **Medium** | `GitHubClient`, `AlertCache`, and all LLM adapters import `settings` directly at module level. This makes unit testing difficult. Pass configuration as constructor parameters instead (dependency injection). |
| 7.3 | **No abstract method enforcements** | `modules/base.py` | **Low** | While `BaseModule` defines the `run()` interface, there are no `@abstractmethod` decorators to enforce implementation in subclasses. Modules that forget to implement `run()` would silently inherit a default. |
| 7.4 | **M3 Query module is stateful, others are stateless** | `modules/m3_query.py` | **Low** | This asymmetry is intentional (conversation memory) but not documented. Consider a `StatefulModule` subclass or explicit interface to clarify the pattern. |
| 7.5 | **Copilot adapter is `NotImplementedError`** | `llm/factory.py` | **Low** | The factory detects Copilot as a provider and attempts instantiation, but the adapter raises `NotImplementedError`. Either remove from detection or implement as a stub that returns a helpful message. |

### Recommended Refactor for 7.1:

```python
# cli/main.py — refactored structure
@click.command()
@click.option("--org", ...)
@click.option("--repo", ...)
@click.option("--list-orgs", ...)
@click.option("--debug", ...)
def cli(org, repo, list_orgs, debug):
    console = Console()
    settings.setup_logging()
    print_banner(console)

    org = resolve_org(console, org, list_orgs)
    llm = select_llm_provider(console)
    context = load_alert_data(console, org, repo)

    interactive_loop(console, llm, context, org, repo)
```

---

## 8. Missing Features & Enhancements

| # | Feature | Priority | Description |
|---|---------|----------|-------------|
| 8.1 | **Prompt template system** | **High** | System prompts are hardcoded strings in each module. Externalise to `prompts/` directory as text files. Enables prompt tuning without code changes. Optionally use Jinja2 (already in requirements) for dynamic prompts with variables. |
| 8.2 | **Structured LLM output (JSON mode)** | **High** | LLM responses are raw text. For triage (M1), remediation (M2), and risk (M4), structured JSON output would enable programmatic use: dashboards, integrations, automated PR creation. |
| 8.3 | **Token count estimation** | **High** | No mechanism to estimate prompt token count before sending to the LLM. Large orgs with thousands of alerts could exceed model context windows. Add `tiktoken` (OpenAI) or approximate counting, and truncate/summarise alert data when approaching limits. |
| 8.4 | **Progress indicators** | **Medium** | During long operations (pagination, LLM calls), the terminal shows no feedback. Add Rich `Progress` bars for pagination and spinners for LLM calls. |
| 8.5 | **Session persistence** | **Medium** | M3 conversation history is lost on exit. Optionally persist to a local file (JSON/SQLite) so users can resume conversations. |
| 8.6 | **Alert filtering** | **Medium** | No way to filter alerts by repository, severity, ecosystem, or date range within the interactive session. Add filter commands: `/filter severity:critical`, `/filter repo:my-app`. |
| 8.7 | **Historical trend snapshots** | **Medium** | Weekly reports note "Trend data not available". Store periodic snapshots of `SecuritySummary` in the cache database to enable week-over-week trend analysis. |
| 8.8 | **Rate-limit pre-check** | **Medium** | Check `X-RateLimit-Remaining` header proactively before starting a large batch of requests. Warn users if quota is low. |
| 8.9 | **Async HTTP support** | **Low** | All HTTP calls are synchronous. For future web/API deployment or scanning many repos in parallel, migrate to `httpx.AsyncClient`. |
| 8.10 | **Configurable max tokens per module** | **Low** | All modules use a hardcoded `max_tokens=2048`. Some modules (M6 Narrator, M1 Triage) may need more tokens for large orgs. Make configurable via `.env` or module-level defaults. |
| 8.11 | **Export conversation history** | **Low** | No way to export the Q&A session as a log file. Useful for audit trails and sharing findings with team members. |

---

## Summary — Priority Action Matrix

### Immediate (Sprint 1 — Must Fix)

| Item | Category | Effort |
|------|----------|--------|
| 1.1 Rate-limit retry bug | Bug | Small |
| 4.1 Ollama error handling | Resilience | Small |
| 4.2 OpenAI retry logic | Resilience | Small |
| 5.1 Add tests for client, router, factory | Testing | Large |
| 2.1 HTML escaping fix | Security | Small |
| 2.2 LLM output sanitisation | Security | Small |

### Short-Term (Sprint 2–3)

| Item | Category | Effort |
|------|----------|--------|
| 3.1 Remove unused dependencies | Quality | Small |
| 6.1 Parallel alert fetching | Performance | Medium |
| 7.1 Refactor cli() god function | Architecture | Medium |
| 4.6 Partial fetch failure handling | Resilience | Medium |
| 8.1 Prompt template system | Feature | Medium |
| 8.3 Token count estimation | Feature | Medium |
| 5.3 GitHub Actions CI pipeline | Testing | Small |

### Medium-Term (Sprint 4–6)

| Item | Category | Effort |
|------|----------|--------|
| 8.2 Structured LLM output | Feature | Large |
| 8.4 Progress indicators | UX | Small |
| 8.5 Session persistence | Feature | Medium |
| 8.6 Alert filtering | Feature | Medium |
| 8.7 Historical trends | Feature | Large |
| 3.2 Consolidate styling code | Quality | Medium |
| 7.2 Dependency injection | Architecture | Large |

---

## Metrics & Targets

| Metric | Current | Target |
|--------|---------|--------|
| Test files | 2 | 12+ |
| Unit tests | ~10 | 70–85 |
| Code coverage | ~8% (estimated) | 80%+ |
| Unused dependencies | 4 | 0 |
| Files using deprecated `datetime.utcnow()` | 5+ | 0 |
| LLM adapters with retry logic | 1 of 4 | 4 of 4 |
| Modules with external prompt templates | 0 of 7 | 7 of 7 |
| CI/CD pipeline | None | GitHub Actions |

---

*End of Improvement Plan*
