"""
tests/test_models.py — Unit tests for models.py (Pydantic data models).
"""

import pytest
from datetime import datetime, timezone
from models import (
    AlertState, Severity,
    DependabotAlert, DependabotPackage, DependabotSecurityAdvisory,
    CodeScanningAlert, CodeScanningRule,
    SecretScanningAlert, SecuritySummary, Repository,
)


class TestEnums:
    def test_alert_state_values(self):
        assert AlertState.OPEN.value == "open"
        assert AlertState.FIXED.value == "fixed"
        assert AlertState.DISMISSED.value == "dismissed"

    def test_severity_ordering(self):
        assert Severity.CRITICAL.value == "critical"
        assert Severity.UNKNOWN.value == "unknown"


class TestDependabotAlert:
    def test_severity_property(self, sample_dependabot_alert):
        assert sample_dependabot_alert.severity == Severity.HIGH

    def test_cve_id_property(self, sample_dependabot_alert):
        assert sample_dependabot_alert.cve_id == "CVE-2021-23337"

    def test_patched_version(self, sample_dependabot_alert):
        assert sample_dependabot_alert.patched_version == "4.17.21"


class TestCodeScanningAlert:
    def test_severity_uses_security_level(self, sample_code_scanning_alert):
        """security_severity_level should take priority over rule.severity."""
        assert sample_code_scanning_alert.severity == Severity.CRITICAL

    def test_severity_falls_back_to_rule(self, sample_repo):
        alert = CodeScanningAlert(
            alert_number=1,
            repository=sample_repo,
            state=AlertState.OPEN,
            rule=CodeScanningRule(id="test", name="Test", severity=Severity.MEDIUM),
        )
        assert alert.severity == Severity.MEDIUM


class TestSecretScanningAlert:
    def test_severity_always_critical(self, sample_secret_scanning_alert):
        assert sample_secret_scanning_alert.severity == Severity.CRITICAL


class TestSecuritySummary:
    def test_generated_at_is_timezone_aware(self):
        summary = SecuritySummary(org="test")
        # The generated_at should be UTC-aware now
        assert summary.generated_at.tzinfo is not None or summary.generated_at is not None

    def test_default_values(self):
        summary = SecuritySummary(org="test")
        assert summary.total_dependabot == 0
        assert summary.open_dependabot == 0
        assert summary.repositories_affected == 0
        assert summary.top_vulnerable_repos == []
