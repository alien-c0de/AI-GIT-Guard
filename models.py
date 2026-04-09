"""
models.py — Pydantic v2 data models for GitHub security alert types.
All API responses are normalised into these domain objects before processing.
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field


# ── Enumerations ────────────────────────────────────────────────────────────

class AlertState(str, Enum):
    OPEN = "open"
    DISMISSED = "dismissed"
    FIXED = "fixed"
    AUTO_DISMISSED = "auto_dismissed"

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    WARNING = "warning"
    NOTE = "note"
    NONE = "none"
    UNKNOWN = "unknown"


# ── Shared sub-models ────────────────────────────────────────────────────────

class Repository(BaseModel):
    id: int
    name: str
    full_name: str
    private: bool = False
    html_url: str = ""
    default_branch: str = "main"

class DismissedReason(BaseModel):
    reason: Optional[str] = None
    comment: Optional[str] = None


# ── Dependabot Alert ─────────────────────────────────────────────────────────

class DependabotPackage(BaseModel):
    ecosystem: str = ""
    name: str = ""

class DependabotSecurityAdvisory(BaseModel):
    ghsa_id: str = ""
    cve_id: Optional[str] = None
    summary: str = ""
    description: str = ""
    severity: Severity = Severity.UNKNOWN
    cvss_score: Optional[float] = None
    cvss_vector: Optional[str] = None
    cwe_ids: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)

class DependabotAlert(BaseModel):
    alert_number: int
    repository: Repository
    state: AlertState
    package: DependabotPackage
    advisory: DependabotSecurityAdvisory
    vulnerable_version_range: str = ""
    patched_version: Optional[str] = None
    auto_dismissed_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    dismissed_reason: Optional[str] = None
    fixed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    html_url: str = ""

    @property
    def severity(self) -> Severity:
        return self.advisory.severity

    @property
    def cve_id(self) -> Optional[str]:
        return self.advisory.cve_id


# ── Code Scanning Alert ──────────────────────────────────────────────────────

class CodeScanningRule(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    severity: Severity = Severity.UNKNOWN
    security_severity_level: Optional[Severity] = None
    tags: List[str] = Field(default_factory=list)

class CodeScanningLocation(BaseModel):
    path: str = ""
    start_line: int = 0
    end_line: int = 0
    start_column: int = 0
    end_column: int = 0

class CodeScanningAlert(BaseModel):
    alert_number: int
    repository: Repository
    state: AlertState
    rule: CodeScanningRule
    tool_name: str = ""
    tool_version: Optional[str] = None
    ref: str = ""          # branch / ref where alert was found
    location: Optional[CodeScanningLocation] = None
    message: str = ""
    dismissed_at: Optional[datetime] = None
    dismissed_reason: Optional[str] = None
    fixed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    html_url: str = ""

    @property
    def severity(self) -> Severity:
        return self.rule.security_severity_level or self.rule.severity


# ── Secret Scanning Alert ────────────────────────────────────────────────────

class SecretScanningAlert(BaseModel):
    alert_number: int
    repository: Repository
    state: AlertState
    secret_type: str = ""
    secret_type_display_name: str = ""
    secret: Optional[str] = None   # Redacted in most API responses
    push_protection_bypassed: bool = False
    push_protection_bypassed_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolved_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    html_url: str = ""

    @property
    def severity(self) -> Severity:
        # Exposed secrets are always treated as Critical
        return Severity.CRITICAL


# ── Aggregated security summary ──────────────────────────────────────────────

class SecuritySummary(BaseModel):
    """High-level counts used by the Narrator and Risk modules."""
    org: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    total_dependabot: int = 0
    open_dependabot: int = 0
    critical_dependabot: int = 0
    high_dependabot: int = 0

    total_code_scanning: int = 0
    open_code_scanning: int = 0
    critical_code_scanning: int = 0
    high_code_scanning: int = 0

    total_secret_scanning: int = 0
    open_secret_scanning: int = 0
    push_protection_bypassed: int = 0

    repositories_affected: int = 0
    top_vulnerable_repos: List[str] = Field(default_factory=list)
    extra: Dict[str, Any] = Field(default_factory=dict)
