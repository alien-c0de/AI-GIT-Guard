"""
llm/github_models_adapter.py — GitHub Models adapter.

Uses models from the GitHub Marketplace (hosted on Azure AI inference).
The endpoint is OpenAI-compatible, so we use the openai SDK with a custom
base_url and the user's GITHUB_TOKEN as the API key.

Docs: https://github.com/marketplace/models
"""

from __future__ import annotations

import logging
from typing import Optional

from llm.base import LLMAdapter, LLMResponse, retry_on_transient
from config import settings

logger = logging.getLogger(__name__)


class GitHubModelsAdapter(LLMAdapter):
    """Adapter for GitHub Marketplace models (Azure AI inference endpoint)."""

    def __init__(self, model: str | None = None):
        from openai import OpenAI  # lazy import

        self._model = model or settings.GITHUB_MODELS_MODEL
        self._client = OpenAI(
            base_url=settings.GITHUB_MODELS_ENDPOINT,
            api_key=settings.GITHUB_TOKEN,
        )
        logger.debug(
            "GitHubModelsAdapter ready — model: %s, endpoint: %s",
            self._model,
            settings.GITHUB_MODELS_ENDPOINT,
        )

    @property
    def provider_name(self) -> str:
        return f"github_models/{self._model}"

    @retry_on_transient()
    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        logger.debug("Sending prompt to GitHub Models (model=%s)", self._model)
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_completion_tokens=max_tokens,
        )
        text = response.choices[0].message.content or ""
        usage = response.usage
        return LLMResponse(
            text=text,
            model=self._model,
            provider="github_models",
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
        )
