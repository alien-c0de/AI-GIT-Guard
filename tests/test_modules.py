"""
tests/test_modules.py — Unit tests for AI analysis modules (M1–M6).
Uses MockLLMAdapter from conftest to verify prompt construction and routing.
"""

import pytest
from modules.m1_triage import TriageModule
from modules.m2_remediation import RemediationModule
from modules.m3_query import NLQueryModule
from modules.m6_narrator import NarratorModule


class TestTriageModule:
    def test_triage_returns_llm_response(self, mock_llm, sample_context):
        adapter = mock_llm("## Top Risks\n1. lodash is critical")
        module = TriageModule(adapter)
        result = module.run(sample_context)
        assert "Top Risks" in result

    def test_triage_sends_alert_data_in_prompt(self, mock_llm, sample_context):
        adapter = mock_llm("analysis")
        module = TriageModule(adapter)
        module.run(sample_context)
        assert len(adapter.calls) == 1
        assert "lodash" in adapter.calls[0]["prompt"]

    def test_triage_with_empty_alerts(self, mock_llm, sample_summary):
        adapter = mock_llm("No alerts found")
        module = TriageModule(adapter)
        ctx = {
            "org": "test-org", "repo": None,
            "dependabot": [], "code_scanning": [], "secret_scanning": [],
            "summary": sample_summary,
        }
        result = module.run(ctx)
        assert isinstance(result, str)


class TestRemediationModule:
    def test_remediation_with_alerts(self, mock_llm, sample_context):
        adapter = mock_llm("Upgrade lodash to 4.17.21: npm install lodash@4.17.21")
        module = RemediationModule(adapter)
        result = module.run(sample_context)
        assert "lodash" in result

    def test_remediation_no_open_alerts(self, mock_llm, sample_summary):
        adapter = mock_llm("should not be called")
        module = RemediationModule(adapter)
        ctx = {
            "org": "test-org", "repo": None,
            "dependabot": [], "code_scanning": [], "secret_scanning": [],
            "summary": sample_summary,
        }
        result = module.run(ctx)
        assert "No open Dependabot alerts" in result
        assert len(adapter.calls) == 0  # LLM should not be called


class TestNLQueryModule:
    def test_query_returns_response(self, mock_llm, sample_context):
        adapter = mock_llm("There are 3 open alerts.")
        module = NLQueryModule(adapter)
        result = module.run(sample_context, query="How many alerts are open?")
        assert "3 open alerts" in result

    def test_query_without_question_returns_help(self, mock_llm, sample_context):
        adapter = mock_llm("")
        module = NLQueryModule(adapter)
        result = module.run(sample_context, query=None)
        assert "Please enter a question" in result
        assert len(adapter.calls) == 0

    def test_query_builds_conversation_history(self, mock_llm, sample_context):
        adapter = mock_llm("Answer 1")
        module = NLQueryModule(adapter)
        module.run(sample_context, query="First question")
        assert len(module._history) == 1

        adapter._response_text = "Answer 2"
        module.run(sample_context, query="Follow-up")
        assert len(module._history) == 2
        # Second call should include history in prompt
        assert "First question" in adapter.calls[1]["prompt"]

    def test_query_includes_org_in_prompt(self, mock_llm, sample_context):
        adapter = mock_llm("response")
        module = NLQueryModule(adapter)
        module.run(sample_context, query="Any question")
        assert "test-org" in adapter.calls[0]["prompt"]


class TestNarratorModule:
    def test_narrator_generates_briefing(self, mock_llm, sample_context):
        adapter = mock_llm("The security posture of test-org is currently HIGH risk.")
        module = NarratorModule(adapter)
        result = module.run(sample_context)
        assert "HIGH risk" in result

    def test_narrator_no_summary(self, mock_llm):
        adapter = mock_llm("")
        module = NarratorModule(adapter)
        ctx = {"org": "test-org", "repo": None, "dependabot": [], "code_scanning": [],
               "secret_scanning": [], "summary": None}
        result = module.run(ctx)
        assert "No summary data available" in result
        assert len(adapter.calls) == 0
