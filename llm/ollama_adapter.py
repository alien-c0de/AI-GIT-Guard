"""
llm/ollama_adapter.py — Ollama local LLM adapter (zero-cost, runs on-prem).
Uses the ollama-python SDK which connects to a local Ollama server.
"""

from __future__ import annotations

import logging
from typing import Optional

from llm.base import LLMAdapter, LLMResponse
from config import settings

logger = logging.getLogger(__name__)


class OllamaAdapter(LLMAdapter):
    """Adapter for locally-running Ollama models (llama3, codellama, mistral, etc.)."""

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
        import ollama  # lazy import — not needed when using other providers
        self._model = model or settings.OLLAMA_MODEL
        self._base_url = base_url or settings.OLLAMA_BASE_URL
        self._client = ollama.Client(host=self._base_url)
        logger.debug("OllamaAdapter ready — model: %s @ %s", self._model, self._base_url)

    @property
    def provider_name(self) -> str:
        return f"ollama/{self._model}"

    def complete(self, prompt: str, system: Optional[str] = None, max_tokens: int = 2048) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        logger.debug("Sending prompt to Ollama (model=%s, ~%d chars)", self._model, len(prompt))
        try:
            response = self._client.chat(
                model=self._model,
                messages=messages,
                options={"num_predict": max_tokens},
            )
        except Exception as exc:
            raise RuntimeError(
                f"Ollama request failed (server={self._base_url}, model={self._model}). "
                f"Ensure Ollama is running ('ollama serve') and the model is pulled "
                f"('ollama pull {self._model}').\n"
                f"Original error: {exc}"
            ) from exc

        text = response.get("message", {}).get("content", "")
        return LLMResponse(
            text=text,
            model=self._model,
            provider="ollama",
        )
