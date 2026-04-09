"""
tests/test_router.py — Unit tests for modules/router.py (Intent Router).
"""

import pytest
from modules.router import IntentRouter, Intent, SLASH_COMMANDS


class TestSlashCommands:
    """Slash commands should map to intents instantly (no LLM call)."""

    @pytest.mark.parametrize("cmd, expected_intent", [
        ("/triage", Intent.TRIAGE),
        ("/remediate", Intent.REMEDIATION),
        ("/risk", Intent.RISK_PREDICTION),
        ("/predict", Intent.RISK_PREDICTION),
        ("/workflow", Intent.WORKFLOW),
        ("/narrate", Intent.NARRATE),
        ("/report", Intent.REPORT),
        ("/fetch", Intent.FETCH),
        ("/refresh", Intent.FETCH),
        ("/help", Intent.HELP),
        ("/clear", Intent.CLEAR),
        ("/cls", Intent.CLEAR),
        ("/exit", Intent.EXIT),
        ("/quit", Intent.EXIT),
    ])
    def test_slash_command_mapping(self, mock_llm, cmd, expected_intent):
        router = IntentRouter(mock_llm())
        intent, args = router.classify(cmd)
        assert intent == expected_intent

    def test_slash_command_with_args(self, mock_llm):
        router = IntentRouter(mock_llm())
        intent, args = router.classify("/report pdf compliance")
        assert intent == Intent.REPORT
        assert args == "pdf compliance"

    def test_slash_command_case_insensitive(self, mock_llm):
        router = IntentRouter(mock_llm())
        intent, _ = router.classify("/TRIAGE")
        assert intent == Intent.TRIAGE


class TestExitKeywords:
    """Common exit words should return EXIT intent without LLM."""

    @pytest.mark.parametrize("keyword", ["exit", "quit", "q", ":q", "bye"])
    def test_exit_keywords(self, mock_llm, keyword):
        router = IntentRouter(mock_llm())
        intent, _ = router.classify(keyword)
        assert intent == Intent.EXIT


class TestNaturalLanguageClassification:
    """Natural language input uses the LLM for classification."""

    def test_llm_returns_triage(self, mock_llm):
        router = IntentRouter(mock_llm("triage"))
        intent, args = router.classify("What are my top risks?")
        assert intent == Intent.TRIAGE
        assert args == "What are my top risks?"

    def test_llm_returns_query(self, mock_llm):
        router = IntentRouter(mock_llm("query"))
        intent, _ = router.classify("How many alerts are open?")
        assert intent == Intent.QUERY

    def test_llm_returns_risk(self, mock_llm):
        router = IntentRouter(mock_llm("risk"))
        intent, _ = router.classify("Which repos are most vulnerable?")
        assert intent == Intent.RISK_PREDICTION

    def test_unrecognised_intent_falls_back_to_query(self, mock_llm):
        router = IntentRouter(mock_llm("banana"))
        intent, _ = router.classify("Something random")
        assert intent == Intent.QUERY

    def test_empty_response_falls_back_to_query(self, mock_llm):
        router = IntentRouter(mock_llm(""))
        intent, _ = router.classify("Hmm")
        assert intent == Intent.QUERY

    def test_llm_exception_falls_back_to_query(self, mock_llm):
        """If the LLM call itself fails, router should default to QUERY."""
        class FailingLLM(mock_llm().__class__):
            def complete(self, prompt, system=None, max_tokens=2048):
                raise RuntimeError("LLM is down")

        router = IntentRouter(FailingLLM())
        intent, _ = router.classify("Any question")
        assert intent == Intent.QUERY


class TestLLMCallCount:
    """Verify slash commands skip the LLM entirely."""

    def test_slash_command_no_llm_call(self, mock_llm):
        adapter = mock_llm()
        router = IntentRouter(adapter)
        router.classify("/triage")
        assert len(adapter.calls) == 0

    def test_natural_language_makes_llm_call(self, mock_llm):
        adapter = mock_llm("query")
        router = IntentRouter(adapter)
        router.classify("How many alerts?")
        assert len(adapter.calls) == 1
