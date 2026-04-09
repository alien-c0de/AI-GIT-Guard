"""
tests/test_factory.py — Unit tests for llm/factory.py (LLM provider factory).
"""

import pytest
from llm.factory import get_llm_adapter


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_llm_adapter("non_existent_provider")


def test_copilot_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="Phase 2"):
        get_llm_adapter("copilot")


def test_provider_case_insensitive():
    """Provider names should be normalised to lowercase."""
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_llm_adapter("NONEXISTENT")
