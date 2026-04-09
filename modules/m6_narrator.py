"""
modules/m6_narrator.py — Module 6: Security Posture Narrator
Generates a plain-English executive narrative summary of the organisation's
security posture — suitable for management reports and CISO briefings.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from modules.base import BaseModule
from models import SecuritySummary

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a security communications expert writing briefings for CISOs and executives.
Write in clear, non-technical prose. Avoid jargon where possible.
Be honest about risks without causing panic. Always end with concrete next steps.
Use a professional but accessible tone."""


class NarratorModule(BaseModule):
    MODULE_ID = "M6"
    MODULE_NAME = "Security Posture Narrator"
    DESCRIPTION = "Generates an executive narrative summary of your organisation's security posture."

    def run(self, context: dict[str, Any], query: Optional[str] = None) -> str:
        summary: Optional[SecuritySummary] = context.get("summary")
        org = context.get("org", "unknown")

        if not summary:
            return "No summary data available. Please fetch alerts first."

        prompt = f"""Write an executive security posture briefing for GitHub organisation: {org}
Date: {datetime.now(timezone.utc).strftime('%B %d, %Y')}

=== SECURITY METRICS ===
DEPENDABOT (Dependency Vulnerabilities):
  - Total alerts: {summary.total_dependabot}
  - Open alerts: {summary.open_dependabot}
  - Critical severity: {summary.critical_dependabot}
  - High severity: {summary.high_dependabot}

CODE SCANNING (SAST / Static Analysis):
  - Total alerts: {summary.total_code_scanning}
  - Open alerts: {summary.open_code_scanning}
  - Critical severity: {summary.critical_code_scanning}
  - High severity: {summary.high_code_scanning}

SECRET SCANNING (Exposed Credentials):
  - Total alerts: {summary.total_secret_scanning}
  - Open (active exposures): {summary.open_secret_scanning}
  - Push protection bypasses: {summary.push_protection_bypassed}

SCOPE:
  - Repositories affected: {summary.repositories_affected}
  - Most vulnerable repos: {', '.join(summary.top_vulnerable_repos) or 'N/A'}

=== INSTRUCTIONS ===
Write a 3-4 paragraph executive briefing covering:
1. Current security posture overview (headline risk level: Critical / High / Medium / Low)
2. Key risks and what they mean for the business
3. Most urgent actions required and by when
4. Recommended longer-term improvements

Do NOT use bullet points — write in flowing professional prose."""

        logger.debug("M6 Narrator: generating executive narrative for org: %s", org)
        response = self._llm.complete(prompt, system=SYSTEM_PROMPT, max_tokens=1500)
        return response.text
