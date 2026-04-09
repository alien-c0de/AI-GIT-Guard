"""
llm/openai_adapter.py — OpenAI GPT adapter (also works with any OpenAI-compatible endpoint).
"""

from __future__ import annotations

import logging
from typing import Optional

from llm.base import LLMAdapter, LLMResponse, retry_on_transient
from config import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o"


class OpenAIAdapter(LLMAdapter):
    """Adapter for OpenAI models (or any OpenAI-compatible API)."""

    def __init__(self, model: str = DEFAULT_MODEL):
        from openai import OpenAI  # lazy import
        self._model = model
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        logger.debug("OpenAIAdapter ready — model: %s", self._model)

    @property
    def provider_name(self) -> str:
        return f"openai/{self._model}"

    @retry_on_transient()
    def complete(self, prompt: str, system: Optional[str] = None, max_tokens: int = 2048) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        logger.debug("Sending prompt to OpenAI (model=%s)", self._model)
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
        )
        text = response.choices[0].message.content or ""
        usage = response.usage
        return LLMResponse(
            text=text,
            model=self._model,
            provider="openai",
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
        )
