"""
llm/base.py — Abstract base class all LLM adapters must implement.
Any module calling the LLM only depends on this interface, never on
provider-specific SDKs directly.
"""

from __future__ import annotations

import functools
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


def retry_on_transient(
    max_retries: int = 3,
    backoff: tuple[int, ...] = (2, 5, 10),
    retryable_codes: set[int] = frozenset({429, 502, 503}),
):
    """Decorator that retries LLM API calls on transient HTTP errors."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_err: Exception | None = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    status = getattr(e, "status_code", None)
                    if status is None or status not in retryable_codes:
                        raise
                    last_err = e
                    wait = backoff[min(attempt, len(backoff) - 1)]
                    logger.warning(
                        "LLM call returned %s (attempt %d/%d). Retrying in %ds…",
                        status, attempt + 1, max_retries, wait,
                    )
                    time.sleep(wait)
            raise last_err  # type: ignore[misc]
        return wrapper
    return decorator


class LLMAdapter(ABC):
    """
    Abstract LLM provider adapter.
    Subclasses: OllamaAdapter, ClaudeAdapter, OpenAIAdapter, CopilotAdapter
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier."""
        ...

    @abstractmethod
    def complete(self, prompt: str, system: Optional[str] = None, max_tokens: int = 2048) -> LLMResponse:
        """
        Send a prompt to the LLM and return the response.

        Args:
            prompt:     User/human turn content.
            system:     Optional system instruction.
            max_tokens: Maximum tokens in the completion.

        Returns:
            LLMResponse with the generated text.
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} provider={self.provider_name}>"
