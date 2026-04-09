"""
llm/claude_adapter.py — Claude API adapter.
Supports both the official Anthropic SDK and OpenRouter (OpenAI-compatible proxy).
When ANTHROPIC_AUTH_TOKEN and ANTHROPIC_BASE_URL are set in .env, the adapter
uses the OpenAI SDK pointed at OpenRouter. Otherwise it uses the native Anthropic SDK.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from llm.base import LLMAdapter, LLMResponse
from config import settings

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-opus-4-5"


class ClaudeAdapter(LLMAdapter):
    """Adapter for Claude via Anthropic SDK or OpenRouter (OpenAI-compatible)."""

    def __init__(self, model: str = CLAUDE_MODEL):
        self._use_openrouter = bool(settings.ANTHROPIC_AUTH_TOKEN and settings.ANTHROPIC_BASE_URL)

        if self._use_openrouter:
            from openai import OpenAI  # OpenRouter uses OpenAI-compatible API
            self._model = settings.ANTHROPIC_MODEL or model
            base_url = settings.ANTHROPIC_BASE_URL.rstrip("/")
            if not base_url.endswith("/v1"):
                base_url += "/v1"
            self._client = OpenAI(
                api_key=settings.ANTHROPIC_AUTH_TOKEN,
                base_url=base_url,
            )
            logger.debug("ClaudeAdapter ready (OpenRouter) — model: %s, base: %s", self._model, base_url)
        else:
            import anthropic  # native Anthropic SDK
            self._model = model
            self._client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            logger.debug("ClaudeAdapter ready (Anthropic) — model: %s", self._model)

    @property
    def provider_name(self) -> str:
        prefix = "openrouter" if self._use_openrouter else "claude"
        return f"{prefix}/{self._model}"

    def complete(self, prompt: str, system: Optional[str] = None, max_tokens: int = 2048) -> LLMResponse:
        logger.debug("Sending prompt to %s (model=%s)", "OpenRouter" if self._use_openrouter else "Claude", self._model)

        if self._use_openrouter:
            return self._complete_openrouter(prompt, system, max_tokens)
        else:
            return self._complete_anthropic(prompt, system, max_tokens)

    _RETRY_ATTEMPTS = 3
    _RETRY_BACKOFF = (2, 5, 10)  # seconds between retries
    _RETRYABLE_CODES = {404, 429, 502, 503}

    def _complete_openrouter(self, prompt: str, system: Optional[str], max_tokens: int) -> LLMResponse:
        """Call OpenRouter via OpenAI-compatible chat completions endpoint.

        Retries automatically on transient provider errors (404, 429, 502, 503)
        that occur when OpenRouter's upstream provider is temporarily unavailable.
        """
        from openai import APIStatusError

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        last_err: Exception | None = None
        for attempt in range(self._RETRY_ATTEMPTS):
            try:
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
                    provider="openrouter",
                    prompt_tokens=usage.prompt_tokens if usage else None,
                    completion_tokens=usage.completion_tokens if usage else None,
                )
            except APIStatusError as e:
                last_err = e
                if e.status_code not in self._RETRYABLE_CODES:
                    raise
                wait = self._RETRY_BACKOFF[min(attempt, len(self._RETRY_BACKOFF) - 1)]
                logger.warning(
                    "OpenRouter returned %s (attempt %d/%d). Retrying in %ds…",
                    e.status_code, attempt + 1, self._RETRY_ATTEMPTS, wait,
                )
                time.sleep(wait)

        raise last_err  # type: ignore[misc]

    def _complete_anthropic(self, prompt: str, system: Optional[str], max_tokens: int) -> LLMResponse:
        """Call the native Anthropic Messages API."""
        kwargs: dict = dict(
            model=self._model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            kwargs["system"] = system

        response = self._client.messages.create(**kwargs)
        text = response.content[0].text if response.content else ""
        return LLMResponse(
            text=text,
            model=self._model,
            provider="claude",
            prompt_tokens=response.usage.input_tokens if response.usage else None,
            completion_tokens=response.usage.output_tokens if response.usage else None,
        )
