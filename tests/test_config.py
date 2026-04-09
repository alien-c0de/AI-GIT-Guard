"""
tests/test_config.py — Unit tests for config.py (Settings singleton).
"""

import os
import pytest


class TestSettingsInit:
    """Test that Settings reads environment variables correctly."""

    def test_default_cache_ttl(self, monkeypatch):
        monkeypatch.delenv("CACHE_TTL_MINUTES", raising=False)
        from config import Settings
        s = Settings()
        assert s.CACHE_TTL_MINUTES == 30

    def test_custom_cache_ttl(self, monkeypatch):
        monkeypatch.setenv("CACHE_TTL_MINUTES", "60")
        from config import Settings
        s = Settings()
        assert s.CACHE_TTL_MINUTES == 60

    def test_invalid_cache_ttl_falls_back(self, monkeypatch):
        monkeypatch.setenv("CACHE_TTL_MINUTES", "not_a_number")
        from config import Settings
        s = Settings()
        assert s.CACHE_TTL_MINUTES == 30

    def test_default_llm_provider(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        from config import Settings
        s = Settings()
        assert s.LLM_PROVIDER == "ollama"

    def test_llm_provider_lowercased(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "Claude")
        from config import Settings
        s = Settings()
        assert s.LLM_PROVIDER == "claude"


class TestSettingsValidation:
    """Test that validate() catches missing required values."""

    def test_missing_github_token_raises(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "")
        monkeypatch.setenv("GITHUB_ORG", "test-org")
        from config import Settings
        s = Settings()
        with pytest.raises(ValueError, match="GITHUB_TOKEN"):
            s.validate()

    def test_missing_github_org_raises(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_valid_token")
        monkeypatch.setenv("GITHUB_ORG", "")
        from config import Settings
        s = Settings()
        with pytest.raises(ValueError, match="GITHUB_ORG"):
            s.validate()

    def test_valid_config_passes(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_valid_token")
        monkeypatch.setenv("GITHUB_ORG", "test-org")
        from config import Settings
        s = Settings()
        s.validate()  # should not raise


class TestProviderDetection:
    """Test detect_available_providers() logic."""

    def test_openai_rejects_placeholder(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-xxxx")
        monkeypatch.setenv("GITHUB_TOKEN", "")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "")
        monkeypatch.setenv("COPILOT_TOKEN", "")
        monkeypatch.setenv("OLLAMA_BASE_URL", "")
        from config import Settings
        s = Settings()
        providers = s.detect_available_providers()
        ids = [p["id"] for p in providers]
        assert "openai" not in ids

    def test_openai_rejects_short_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-short")
        monkeypatch.setenv("GITHUB_TOKEN", "")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "")
        monkeypatch.setenv("COPILOT_TOKEN", "")
        monkeypatch.setenv("OLLAMA_BASE_URL", "")
        from config import Settings
        s = Settings()
        providers = s.detect_available_providers()
        ids = [p["id"] for p in providers]
        assert "openai" not in ids

    def test_github_models_detected_when_token_present(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_valid_token")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "")
        monkeypatch.setenv("OPENAI_API_KEY", "")
        monkeypatch.setenv("COPILOT_TOKEN", "")
        monkeypatch.setenv("OLLAMA_BASE_URL", "")
        from config import Settings
        s = Settings()
        providers = s.detect_available_providers()
        ids = [p["id"] for p in providers]
        assert "github_models" in ids
