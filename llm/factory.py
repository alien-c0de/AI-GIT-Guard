"""
llm/factory.py -- Returns the correct LLMAdapter based on LLM_PROVIDER setting.
All calling code uses: `from llm.factory import get_llm_adapter`
"""

from __future__ import annotations
from config import settings
from llm.base import LLMAdapter


def get_llm_adapter(provider: str | None = None) -> LLMAdapter:
    """Instantiate and return the LLM adapter for the given (or configured) provider."""
    provider = (provider or settings.LLM_PROVIDER).lower()

    if provider == "ollama":
        from llm.ollama_adapter import OllamaAdapter
        return OllamaAdapter()
    elif provider == "claude":
        from llm.claude_adapter import ClaudeAdapter
        return ClaudeAdapter()
    elif provider == "openai":
        from llm.openai_adapter import OpenAIAdapter
        return OpenAIAdapter()
    elif provider == "github_models":
        from llm.github_models_adapter import GitHubModelsAdapter
        return GitHubModelsAdapter()
    elif provider == "copilot":
        raise NotImplementedError("Copilot adapter is planned for Phase 2.")
    else:
        raise ValueError(f"Unknown LLM provider: '{provider}'. Expected: ollama | claude | openai | github_models | copilot")
