"""
tests/conftest.py — Shared fixtures for all AI Git Guard tests.
"""

import pytest
from models import (
    AlertState, Severity, Repository,
    DependabotAlert, DependabotPackage, DependabotSecurityAdvisory,
    CodeScanningAlert, CodeScanningRule, CodeScanningLocation,
    SecretScanningAlert, SecuritySummary,
)
from llm.base import LLMAdapter, LLMResponse


# ── Mock LLM Adapter ────────────────────────────────────────────────────────

class MockLLMAdapter(LLMAdapter):
    """Deterministic LLM adapter for tests — returns a configurable response."""

    def __init__(self, response_text: str = "mock response"):
        self._response_text = response_text
        self.calls: list[dict] = []  # records all calls for assertions

    @property
    def provider_name(self) -> str:
        return "mock/test"

    def complete(self, prompt: str, system: str | None = None, max_tokens: int = 2048) -> LLMResponse:
        self.calls.append({"prompt": prompt, "system": system, "max_tokens": max_tokens})
        return LLMResponse(text=self._response_text, model="mock", provider="mock")


@pytest.fixture
def mock_llm():
    """Return a MockLLMAdapter factory — call with optional response text."""
    def _factory(response_text: str = "mock response") -> MockLLMAdapter:
        return MockLLMAdapter(response_text)
    return _factory


# ── Sample Data Fixtures ────────────────────────────────────────────────────

@pytest.fixture
def sample_repo():
    return Repository(id=1, name="test-repo", full_name="org/test-repo", private=False,
                      html_url="https://github.com/org/test-repo", default_branch="main")


@pytest.fixture
def sample_dependabot_alert(sample_repo):
    return DependabotAlert(
        alert_number=42,
        repository=sample_repo,
        state=AlertState.OPEN,
        package=DependabotPackage(ecosystem="npm", name="lodash"),
        advisory=DependabotSecurityAdvisory(
            ghsa_id="GHSA-xxxx-yyyy-zzzz",
            cve_id="CVE-2021-23337",
            summary="Prototype Pollution in lodash",
            description="lodash before 4.17.21 has prototype pollution",
            severity=Severity.HIGH,
            cvss_score=7.2,
            cvss_vector="CVSS:3.1/AV:N/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:H",
            cwe_ids=["CWE-1321"],
        ),
        vulnerable_version_range="< 4.17.21",
        patched_version="4.17.21",
        html_url="https://github.com/org/test-repo/security/dependabot/42",
    )


@pytest.fixture
def sample_code_scanning_alert(sample_repo):
    return CodeScanningAlert(
        alert_number=7,
        repository=sample_repo,
        state=AlertState.OPEN,
        rule=CodeScanningRule(
            id="sql-injection",
            name="SQL Injection",
            description="User input used in SQL query without sanitisation",
            severity=Severity.HIGH,
            security_severity_level=Severity.CRITICAL,
            tags=["security", "cwe-89"],
        ),
        tool_name="CodeQL",
        location=CodeScanningLocation(path="src/db.py", start_line=42, end_line=42),
        message="SQL injection vulnerability",
        html_url="https://github.com/org/test-repo/security/code-scanning/7",
    )


@pytest.fixture
def sample_secret_scanning_alert(sample_repo):
    return SecretScanningAlert(
        alert_number=3,
        repository=sample_repo,
        state=AlertState.OPEN,
        secret_type="aws_access_key_id",
        secret_type_display_name="AWS Access Key ID",
        push_protection_bypassed=False,
        html_url="https://github.com/org/test-repo/security/secret-scanning/3",
    )


@pytest.fixture
def sample_summary():
    return SecuritySummary(
        org="test-org",
        total_dependabot=5,
        open_dependabot=3,
        critical_dependabot=1,
        high_dependabot=2,
        total_code_scanning=4,
        open_code_scanning=2,
        critical_code_scanning=1,
        high_code_scanning=1,
        total_secret_scanning=2,
        open_secret_scanning=1,
        push_protection_bypassed=0,
        repositories_affected=3,
        top_vulnerable_repos=["test-repo", "api-service"],
    )


@pytest.fixture
def sample_context(sample_dependabot_alert, sample_code_scanning_alert,
                   sample_secret_scanning_alert, sample_summary):
    return {
        "org": "test-org",
        "repo": None,
        "dependabot": [sample_dependabot_alert],
        "code_scanning": [sample_code_scanning_alert],
        "secret_scanning": [sample_secret_scanning_alert],
        "summary": sample_summary,
    }
