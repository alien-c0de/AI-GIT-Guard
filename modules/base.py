"""
modules/base.py — Abstract base class for all AI analysis modules.
Each module receives an LLMAdapter and alert data; returns a string result.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from llm.base import LLMAdapter


class BaseModule(ABC):
    """
    Base class for AI Git Guard analysis modules.
    """

    MODULE_ID: str = ""        # e.g. "M1"
    MODULE_NAME: str = ""      # e.g. "Alert Triage & Prioritization"
    DESCRIPTION: str = ""      # One-line description for the help menu

    def __init__(self, llm: LLMAdapter):
        self._llm = llm

    @abstractmethod
    def run(self, context: dict[str, Any], query: Optional[str] = None) -> str:
        """
        Execute the module.

        Args:
            context: Dict containing fetched alert data and summary.
                     Keys: 'dependabot', 'code_scanning', 'secret_scanning', 'summary', 'org'
            query:   Optional natural-language user query (used by M3 NL Query Engine).

        Returns:
            Formatted string output ready for display or rendering.
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.MODULE_ID}: {self.MODULE_NAME}>"
