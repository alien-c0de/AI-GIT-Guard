"""
modules/m1_triage.py — Module 1: Alert Triage & Prioritization
Ranks open security alerts by severity, exploitability, and business impact.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from modules.base import BaseModule
from models import AlertState, Severity

logger = logging.getLogger(__name__)

SEVERITY_RANK = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.WARNING: 4,
    Severity.NOTE: 5,
    Severity.NONE: 6,
    Severity.UNKNOWN: 7,
}

SYSTEM_PROMPT = """You are a senior application security engineer expert in GitHub Advanced Security.
Your job is to triage and prioritise security alerts for a software organisation.
Be concise, actionable, and rank by real-world exploitability and business impact.
Always respond in plain English suitable for a security team standup."""


class TriageModule(BaseModule):
    MODULE_ID = "M1"
    MODULE_NAME = "Alert Triage & Prioritization"
    DESCRIPTION = "Ranks open alerts by severity, CVE score, and exploitability."

    def run(self, context: dict[str, Any], query: Optional[str] = None) -> str:
        dependabot = [a for a in context.get("dependabot", []) if a.state == AlertState.OPEN]
        code_scan  = [a for a in context.get("code_scanning", []) if a.state == AlertState.OPEN]
        secret_scan = [a for a in context.get("secret_scanning", []) if a.state == AlertState.OPEN]

        # Sort by severity rank
        dependabot.sort(key=lambda a: SEVERITY_RANK.get(a.severity, 9))
        code_scan.sort(key=lambda a: SEVERITY_RANK.get(a.severity, 9))

        # Build compact alert summary for the prompt
        dep_lines = [
            f"- [{a.severity.value.upper()}] {a.package.name} ({a.advisory.cve_id or a.advisory.ghsa_id}) "
            f"in {a.repository.name} — {a.advisory.summary[:100]}"
            for a in dependabot[:20]
        ]
        cs_lines = [
            f"- [{a.severity.value.upper()}] {a.rule.name} in {a.repository.name}/{a.location.path if a.location else 'unknown'}"
            for a in code_scan[:20]
        ]
        ss_lines = [
            f"- [CRITICAL] Exposed {a.secret_type_display_name or a.secret_type} in {a.repository.name}"
            + (" [PUSH PROTECTION BYPASSED]" if a.push_protection_bypassed else "")
            for a in secret_scan[:10]
        ]

        prompt = f"""You are analysing security alerts for GitHub organisation: {context.get('org', 'unknown')}.

=== OPEN DEPENDABOT ALERTS (top 20) ===
{chr(10).join(dep_lines) if dep_lines else 'None'}

=== OPEN CODE SCANNING ALERTS (top 20) ===
{chr(10).join(cs_lines) if cs_lines else 'None'}

=== OPEN SECRET SCANNING ALERTS ===
{chr(10).join(ss_lines) if ss_lines else 'None'}

Please produce a prioritised triage report with:
1. TOP 5 IMMEDIATE ACTIONS (must fix today)
2. HIGH PRIORITY (fix this week)
3. MEDIUM / LOW (schedule in backlog)
4. A brief explanation of the most critical risk

Be specific — mention alert names, repos, and CVE IDs where available."""

        logger.debug("M1 Triage: running LLM analysis on %d dep + %d cs + %d ss alerts",
                     len(dependabot), len(code_scan), len(secret_scan))
        response = self._llm.complete(prompt, system=SYSTEM_PROMPT)
        return response.text
