"""
tests/test_aggregator.py — Unit tests for github/aggregator.py
Tests that raw API JSON is correctly parsed into Pydantic domain models.
"""

import pytest
from github.aggregator import (
    parse_dependabot_alert,
    parse_code_scanning_alert,
    parse_secret_scanning_alert,
    build_summary,
)
from models import AlertState, Severity


REPO_RAW = {
    "id": 123,
    "name": "my-app",
    "full_name": "my-org/my-app",
    "private": True,
    "html_url": "https://github.com/my-org/my-app",
    "default_branch": "main",
}


# ── Dependabot ───────────────────────────────────────────────────────────────

DEPENDABOT_RAW = {
    "number": 42,
    "state": "open",
    "repository": REPO_RAW,
    "dependency": {"package": {"ecosystem": "npm", "name": "lodash"}},
    "security_advisory": {
        "ghsa_id": "GHSA-xxxx-yyyy-zzzz",
        "cve_id": "CVE-2021-23337",
        "summary": "Prototype Pollution in lodash",
        "description": "...",
        "severity": "high",
        "cvss": {"score": 7.2, "vector_string": "CVSS:3.1/AV:N/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:H"},
        "cwes": [{"cwe_id": "CWE-1321"}],
        "references": [{"url": "https://nvd.nist.gov/vuln/detail/CVE-2021-23337"}],
    },
    "security_vulnerability": {
        "vulnerable_version_range": "< 4.17.21",
        "first_patched_version": {"identifier": "4.17.21"},
    },
    "html_url": "https://github.com/my-org/my-app/security/dependabot/42",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z",
    "dismissed_at": None,
    "fixed_at": None,
    "auto_dismissed_at": None,
}


def test_parse_dependabot_alert_basic():
    alert = parse_dependabot_alert(DEPENDABOT_RAW)
    assert alert.alert_number == 42
    assert alert.state == AlertState.OPEN
    assert alert.package.name == "lodash"
    assert alert.package.ecosystem == "npm"
    assert alert.advisory.cve_id == "CVE-2021-23337"
    assert alert.advisory.severity == Severity.HIGH
    assert alert.advisory.cvss_score == 7.2
    assert alert.patched_version == "4.17.21"
    assert alert.repository.name == "my-app"


def test_parse_dependabot_alert_severity_property():
    alert = parse_dependabot_alert(DEPENDABOT_RAW)
    assert alert.severity == Severity.HIGH


# ── Code Scanning ────────────────────────────────────────────────────────────

CODE_SCAN_RAW = {
    "number": 7,
    "state": "open",
    "repository": REPO_RAW,
    "rule": {
        "id": "java/sql-injection",
        "name": "SQL Injection",
        "description": "Unsanitized input in SQL query",
        "severity": "error",
        "security_severity_level": "critical",
        "tags": ["security", "correctness"],
    },
    "tool": {"name": "CodeQL", "version": "2.15.0"},
    "ref": "refs/heads/main",
    "most_recent_instance": {
        "location": {
            "path": "src/db/query.java",
            "start_line": 42,
            "end_line": 42,
            "start_column": 10,
            "end_column": 55,
        },
        "message": {"text": "Query built from user input without sanitisation"},
    },
    "html_url": "https://github.com/my-org/my-app/security/code-scanning/7",
    "created_at": "2024-02-01T08:00:00Z",
    "updated_at": "2024-02-01T08:00:00Z",
    "dismissed_at": None,
    "fixed_at": None,
}


def test_parse_code_scanning_alert():
    alert = parse_code_scanning_alert(CODE_SCAN_RAW)
    assert alert.alert_number == 7
    assert alert.state == AlertState.OPEN
    assert alert.rule.id == "java/sql-injection"
    assert alert.rule.name == "SQL Injection"
    assert alert.severity == Severity.CRITICAL
    assert alert.tool_name == "CodeQL"
    assert alert.location is not None
    assert alert.location.path == "src/db/query.java"
    assert alert.location.start_line == 42


# ── Secret Scanning ──────────────────────────────────────────────────────────

SECRET_SCAN_RAW = {
    "number": 3,
    "state": "open",
    "repository": REPO_RAW,
    "secret_type": "aws_access_key_id",
    "secret_type_display_name": "AWS Access Key ID",
    "secret": None,
    "push_protection_bypassed": True,
    "push_protection_bypassed_at": "2024-03-01T12:00:00Z",
    "resolution": None,
    "resolved_at": None,
    "created_at": "2024-03-01T12:00:00Z",
    "updated_at": "2024-03-01T12:00:00Z",
    "html_url": "https://github.com/my-org/my-app/security/secret-scanning/3",
}


def test_parse_secret_scanning_alert():
    alert = parse_secret_scanning_alert(SECRET_SCAN_RAW)
    assert alert.alert_number == 3
    assert alert.state == AlertState.OPEN
    assert alert.secret_type == "aws_access_key_id"
    assert alert.push_protection_bypassed is True
    assert alert.severity == Severity.CRITICAL  # always CRITICAL


# ── Summary builder ──────────────────────────────────────────────────────────

def test_build_summary():
    dep = [parse_dependabot_alert(DEPENDABOT_RAW)]
    cs  = [parse_code_scanning_alert(CODE_SCAN_RAW)]
    ss  = [parse_secret_scanning_alert(SECRET_SCAN_RAW)]

    summary = build_summary("my-org", dep, cs, ss)
    assert summary.org == "my-org"
    assert summary.total_dependabot == 1
    assert summary.open_dependabot == 1
    assert summary.high_dependabot == 1
    assert summary.total_code_scanning == 1
    assert summary.critical_code_scanning == 1
    assert summary.total_secret_scanning == 1
    assert summary.open_secret_scanning == 1
    assert summary.push_protection_bypassed == 1
    assert summary.repositories_affected == 1
    assert "my-org/my-app" in summary.top_vulnerable_repos
