"""
modules/m3_query.py — Module 3: Natural Language Query Engine
Answers free-form security questions about the fetched alert data.
This is the primary interactive module used in the chat loop.
Supports conversation history for multi-turn context.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from modules.base import BaseModule

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are AI Git Guard, an expert GitHub Advanced Security analyst assistant.
You have been given structured security alert data for a GitHub organisation.
Answer the user's question accurately, concisely, and in plain English.
When referencing specific alerts, include repository names and CVE/rule IDs.
If you cannot answer from the data provided, say so — do not hallucinate.
You may reference earlier messages in the conversation if relevant."""

# Maximum number of history exchanges to include in context
MAX_HISTORY = 10


class NLQueryModule(BaseModule):
    MODULE_ID = "M3"
    MODULE_NAME = "Natural Language Query Engine"
    DESCRIPTION = "Answer free-form security questions about your alerts in plain English."

    def __init__(self, llm):
        super().__init__(llm)
        self._history: list[tuple[str, str]] = []  # (user_query, ai_response)

    def run(self, context: dict[str, Any], query: Optional[str] = None) -> str:
        if not query:
            return "Please enter a question. Example: 'How many critical Dependabot alerts are open?'"

        org = context.get("org", "unknown")

        # Build context snapshot for the LLM
        dep = context.get("dependabot", [])
        cs  = context.get("code_scanning", [])
        ss  = context.get("secret_scanning", [])

        context_block = f"""=== SECURITY CONTEXT FOR ORG: {org} ===

DEPENDABOT SUMMARY: {len(dep)} total alerts
{self._dep_summary(dep)}

CODE SCANNING SUMMARY: {len(cs)} total alerts
{self._cs_summary(cs)}

SECRET SCANNING SUMMARY: {len(ss)} total alerts
{self._ss_summary(ss)}
"""

        # Build conversation history block
        history_block = ""
        if self._history:
            recent = self._history[-MAX_HISTORY:]
            exchanges = []
            for user_q, ai_a in recent:
                exchanges.append(f"User: {user_q}\nAssistant: {ai_a}")
            history_block = "\n=== CONVERSATION HISTORY ===\n" + "\n---\n".join(exchanges) + "\n"

        prompt = f"""{context_block}
{history_block}
USER QUESTION: {query}

Answer the question directly based on the data and conversation history above. Be specific and concise."""

        logger.debug("M3 Query: '%s'", query[:80])
        response = self._llm.complete(prompt, system=SYSTEM_PROMPT)

        # Store in history
        self._history.append((query, response.text))

        return response.text

    def _dep_summary(self, alerts: list) -> str:
        from models import AlertState, Severity
        open_a = [a for a in alerts if a.state == AlertState.OPEN]
        crits  = [a for a in open_a if a.severity == Severity.CRITICAL]
        highs  = [a for a in open_a if a.severity == Severity.HIGH]
        lines  = [f"  Open: {len(open_a)}, Critical: {len(crits)}, High: {len(highs)}"]
        for a in crits[:5]:
            lines.append(f"  - [{a.repository.name}] {a.package.name} — {a.advisory.cve_id or a.advisory.ghsa_id}")
        return "\n".join(lines)

    def _cs_summary(self, alerts: list) -> str:
        from models import AlertState, Severity
        open_a = [a for a in alerts if a.state == AlertState.OPEN]
        crits  = [a for a in open_a if a.severity == Severity.CRITICAL]
        lines  = [f"  Open: {len(open_a)}, Critical: {len(crits)}"]
        for a in crits[:5]:
            lines.append(f"  - [{a.repository.name}] {a.rule.name}")
        return "\n".join(lines)

    def _ss_summary(self, alerts: list) -> str:
        from models import AlertState
        open_a   = [a for a in alerts if a.state == AlertState.OPEN]
        bypassed = [a for a in alerts if a.push_protection_bypassed]
        lines    = [f"  Open: {len(open_a)}, Push Protection Bypassed: {len(bypassed)}"]
        for a in open_a[:5]:
            lines.append(f"  - [{a.repository.name}] {a.secret_type_display_name or a.secret_type}")
        return "\n".join(lines)
