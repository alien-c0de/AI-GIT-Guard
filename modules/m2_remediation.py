"""
modules/m2_remediation.py — Module 2: Code Remediation Generator (Phase 2)
Generates AI-powered fix suggestions and (in Phase 2) auto-PR content.
"""

from __future__ import annotations
from typing import Any, Optional
from modules.base import BaseModule
from models import AlertState


class RemediationModule(BaseModule):
    MODULE_ID = "M2"
    MODULE_NAME = "Code Remediation Generator"
    DESCRIPTION = "Generates fix suggestions for vulnerable dependencies and code issues. (Phase 2)"

    def run(self, context: dict[str, Any], query: Optional[str] = None) -> str:
        # Phase 1: basic remediation advice via LLM
        dep = [a for a in context.get("dependabot", []) if a.state == AlertState.OPEN]
        if not dep:
            return "No open Dependabot alerts found to generate remediation advice for."

        top = dep[:10]
        lines = [
            f"- {a.package.name} ({a.advisory.cve_id or a.advisory.ghsa_id}): "
            f"upgrade to {a.patched_version or 'latest patched version'} — {a.advisory.summary[:80]}"
            for a in top
        ]
        prompt = (
            f"Provide specific remediation steps for these vulnerable packages:\n"
            + "\n".join(lines)
            + "\n\nFor each: explain the risk and give the exact upgrade command (npm/pip/maven/gradle)."
        )
        response = self._llm.complete(prompt)
        return response.text
