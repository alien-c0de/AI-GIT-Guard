"""
github/aggregator.py — Normalises raw GitHub API JSON into domain Pydantic models.
Also computes the SecuritySummary roll-up used by Narrator and Risk modules.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from models import (
    AlertState, Severity, Repository,
    DependabotPackage, DependabotSecurityAdvisory, DependabotAlert,
    CodeScanningRule, CodeScanningLocation, CodeScanningAlert,
    SecretScanningAlert, SecuritySummary,
)

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

def _severity(value: Optional[str]) -> Severity:
    if not value:
        return Severity.UNKNOWN
    try:
        return Severity(value.lower())
    except ValueError:
        return Severity.UNKNOWN

def _state(value: Optional[str]) -> AlertState:
    if not value:
        return AlertState.OPEN
    try:
        return AlertState(value.lower())
    except ValueError:
        return AlertState.OPEN

def _repo(raw: dict) -> Repository:
    return Repository(
        id=raw.get("id", 0),
        name=raw.get("name", ""),
        full_name=raw.get("full_name", ""),
        private=raw.get("private", False),
        html_url=raw.get("html_url", ""),
        default_branch=raw.get("default_branch", "main"),
    )


# ── Dependabot ───────────────────────────────────────────────────────────────

def parse_dependabot_alert(raw: dict) -> DependabotAlert:
    adv = raw.get("security_advisory") or {}
    cvss = adv.get("cvss") or {}
    pkg_raw = (raw.get("dependency") or {}).get("package") or {}
    cwe_list = [c.get("cwe_id", "") for c in adv.get("cwes") or []]
    refs = [r.get("url", "") for r in adv.get("references") or []]

    return DependabotAlert(
        alert_number=raw.get("number", 0),
        repository=_repo(raw.get("repository") or {}),
        state=_state(raw.get("state")),
        package=DependabotPackage(
            ecosystem=pkg_raw.get("ecosystem", ""),
            name=pkg_raw.get("name", ""),
        ),
        advisory=DependabotSecurityAdvisory(
            ghsa_id=adv.get("ghsa_id", ""),
            cve_id=adv.get("cve_id"),
            summary=adv.get("summary", ""),
            description=adv.get("description", ""),
            severity=_severity(adv.get("severity")),
            cvss_score=cvss.get("score"),
            cvss_vector=cvss.get("vector_string"),
            cwe_ids=cwe_list,
            references=refs,
        ),
        vulnerable_version_range=(raw.get("security_vulnerability") or {}).get("vulnerable_version_range", ""),
        patched_version=((raw.get("security_vulnerability") or {}).get("first_patched_version") or {}).get("identifier") if raw.get("security_vulnerability") else None,
        dismissed_at=_dt(raw.get("dismissed_at")),
        dismissed_reason=raw.get("dismissed_reason"),
        fixed_at=_dt(raw.get("fixed_at")),
        auto_dismissed_at=_dt(raw.get("auto_dismissed_at")),
        created_at=_dt(raw.get("created_at")),
        updated_at=_dt(raw.get("updated_at")),
        html_url=raw.get("html_url", ""),
    )


# ── Code Scanning ────────────────────────────────────────────────────────────

def parse_code_scanning_alert(raw: dict) -> CodeScanningAlert:
    rule = raw.get("rule") or {}
    tool = raw.get("tool") or {}
    loc_raw = (raw.get("most_recent_instance") or {}).get("location") or {}
    msg = ((raw.get("most_recent_instance") or {}).get("message") or {}).get("text", "")

    location = None
    if loc_raw:
        location = CodeScanningLocation(
            path=loc_raw.get("path", ""),
            start_line=loc_raw.get("start_line", 0),
            end_line=loc_raw.get("end_line", 0),
            start_column=loc_raw.get("start_column", 0),
            end_column=loc_raw.get("end_column", 0),
        )

    return CodeScanningAlert(
        alert_number=raw.get("number", 0),
        repository=_repo(raw.get("repository") or {}),
        state=_state(raw.get("state")),
        rule=CodeScanningRule(
            id=rule.get("id", ""),
            name=rule.get("name", ""),
            description=rule.get("description", ""),
            severity=_severity(rule.get("severity")),
            security_severity_level=_severity(rule.get("security_severity_level")) if rule.get("security_severity_level") else None,
            tags=rule.get("tags") or [],
        ),
        tool_name=tool.get("name", ""),
        tool_version=tool.get("version"),
        ref=raw.get("ref", ""),
        location=location,
        message=msg,
        dismissed_at=_dt(raw.get("dismissed_at")),
        dismissed_reason=raw.get("dismissed_reason"),
        fixed_at=_dt(raw.get("fixed_at")),
        created_at=_dt(raw.get("created_at")),
        updated_at=_dt(raw.get("updated_at")),
        html_url=raw.get("html_url", ""),
    )


# ── Secret Scanning ──────────────────────────────────────────────────────────

def parse_secret_scanning_alert(raw: dict) -> SecretScanningAlert:
    return SecretScanningAlert(
        alert_number=raw.get("number", 0),
        repository=_repo(raw.get("repository") or {}),
        state=_state(raw.get("state")),
        secret_type=raw.get("secret_type", ""),
        secret_type_display_name=raw.get("secret_type_display_name", ""),
        secret=raw.get("secret"),
        push_protection_bypassed=raw.get("push_protection_bypassed", False),
        push_protection_bypassed_at=_dt(raw.get("push_protection_bypassed_at")),
        resolved_at=_dt(raw.get("resolved_at")),
        resolved_reason=raw.get("resolution"),
        created_at=_dt(raw.get("created_at")),
        updated_at=_dt(raw.get("updated_at")),
        html_url=raw.get("html_url", ""),
    )


# ── SecuritySummary builder ──────────────────────────────────────────────────

def build_summary(
    org: str,
    dependabot: list[DependabotAlert],
    code_scanning: list[CodeScanningAlert],
    secret_scanning: list[SecretScanningAlert],
) -> SecuritySummary:
    """Aggregate all fetched alerts into a SecuritySummary roll-up."""
    from collections import Counter

    repo_counter: Counter = Counter()

    # Dependabot stats
    open_dep = [a for a in dependabot if a.state == AlertState.OPEN]
    crit_dep = [a for a in open_dep if a.severity == Severity.CRITICAL]
    high_dep = [a for a in open_dep if a.severity == Severity.HIGH]
    for a in dependabot:
        repo_counter[a.repository.full_name] += 1

    # Code scanning stats
    open_cs = [a for a in code_scanning if a.state == AlertState.OPEN]
    crit_cs = [a for a in open_cs if a.severity == Severity.CRITICAL]
    high_cs = [a for a in open_cs if a.severity == Severity.HIGH]
    for a in code_scanning:
        repo_counter[a.repository.full_name] += 1

    # Secret scanning stats
    open_ss = [a for a in secret_scanning if a.state == AlertState.OPEN]
    bypassed = [a for a in secret_scanning if a.push_protection_bypassed]
    for a in secret_scanning:
        repo_counter[a.repository.full_name] += 1

    top_repos = [r for r, _ in repo_counter.most_common(5)]

    return SecuritySummary(
        org=org,
        total_dependabot=len(dependabot),
        open_dependabot=len(open_dep),
        critical_dependabot=len(crit_dep),
        high_dependabot=len(high_dep),
        total_code_scanning=len(code_scanning),
        open_code_scanning=len(open_cs),
        critical_code_scanning=len(crit_cs),
        high_code_scanning=len(high_cs),
        total_secret_scanning=len(secret_scanning),
        open_secret_scanning=len(open_ss),
        push_protection_bypassed=len(bypassed),
        repositories_affected=len(repo_counter),
        top_vulnerable_repos=top_repos,
    )
