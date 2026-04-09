"""
modules/router.py — Intent Router
Uses the LLM to classify user input and route to the correct module.
Also supports direct /slash commands for power users.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional

from llm.base import LLMAdapter, LLMResponse

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    TRIAGE = "triage"
    REMEDIATION = "remediation"
    QUERY = "query"
    RISK_PREDICTION = "risk"
    WORKFLOW = "workflow"
    NARRATE = "narrate"
    FETCH = "fetch"
    REPORT = "report"
    HELP = "help"
    CLEAR = "clear"
    EXIT = "exit"
    UNKNOWN = "unknown"


# Slash commands mapped to intents
SLASH_COMMANDS: dict[str, Intent] = {
    "/triage": Intent.TRIAGE,
    "/remediate": Intent.REMEDIATION,
    "/risk": Intent.RISK_PREDICTION,
    "/predict": Intent.RISK_PREDICTION,
    "/workflow": Intent.WORKFLOW,
    "/narrate": Intent.NARRATE,
    "/report": Intent.REPORT,
    "/fetch": Intent.FETCH,
    "/refresh": Intent.FETCH,
    "/help": Intent.HELP,
    "/clear": Intent.CLEAR,
    "/cls": Intent.CLEAR,
    "/exit": Intent.EXIT,
    "/quit": Intent.EXIT,
}

ROUTER_SYSTEM_PROMPT = """You are an intent classifier for a GitHub security tool.
Classify the user's message into exactly ONE of these categories:
- triage: user wants to see prioritised/ranked alerts, top risks, what to fix first
- remediation: user wants fix commands, upgrade instructions, how to patch vulnerabilities
- risk: user wants risk prediction, risk assessment, risk scores, proactive risk analysis, or trend-based predictions
- workflow: user wants to analyse GitHub Actions workflow files, CI/CD pipeline security, or YAML workflow review
- narrate: user wants an executive summary, management briefing, posture overview, PDF/HTML report
- query: user is asking a specific question about their alerts, counts, repos, or details
- report: user wants to export/save a report in a specific format (pdf, html, excel)
- fetch: user wants to refresh/reload alert data from GitHub
- help: user wants to know what commands or capabilities are available
- exit: user wants to quit/exit

Respond with ONLY the category name, nothing else. For example: query"""


class IntentRouter:
    """Classifies user input into an Intent using the LLM or slash commands."""

    def __init__(self, llm: LLMAdapter):
        self._llm = llm

    def classify(self, user_input: str) -> tuple[Intent, str]:
        """
        Returns (Intent, remaining_args).
        For slash commands, parsing is instant (no LLM call).
        For natural language, the LLM classifies the intent.
        """
        stripped = user_input.strip()

        # Check exit keywords
        if stripped.lower() in ("exit", "quit", "q", ":q", "bye"):
            return Intent.EXIT, ""

        # Check slash commands
        parts = stripped.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in SLASH_COMMANDS:
            return SLASH_COMMANDS[cmd], args

        # LLM-based classification
        try:
            response = self._llm.complete(
                prompt=f"User message: {stripped}",
                system=ROUTER_SYSTEM_PROMPT,
                max_tokens=20,
            )
            intent_str = response.text.strip().lower().split()[0] if response.text else "query"
            try:
                return Intent(intent_str), stripped
            except ValueError:
                # Default to query for unrecognised intents
                return Intent.QUERY, stripped
        except Exception as e:
            logger.debug("Intent classification failed: %s — defaulting to query", e)
            return Intent.QUERY, stripped
