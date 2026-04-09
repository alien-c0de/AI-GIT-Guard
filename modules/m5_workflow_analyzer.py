"""
modules/m5_workflow_analyzer.py — Module 5: AI GitHub Actions Workflow Analyzer
Analyses GitHub Actions workflow YAML files for security risks such as
script injection, overly broad permissions, pull_request_target misuse,
untrusted input usage, and insecure third-party action references.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from modules.base import BaseModule

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior DevSecOps engineer and GitHub Actions security expert.
You analyse CI/CD workflow YAML files for security vulnerabilities, misconfigurations,
and risky patterns. Your analysis must be thorough, specific, and developer-friendly.
For each issue found, explain the risk clearly and provide a corrected YAML snippet.
Reference GitHub's official security hardening guide for Actions where relevant.
Common risks to check:
- Script injection via untrusted context expressions (github.event.*, github.head_ref, etc.)
- Overly broad permissions (write-all, contents:write when not needed)
- pull_request_target misuse (checking out PR head in a privileged context)
- Unpinned third-party actions (using @main or @master instead of SHA)
- Secrets exposed in logs or passed unsafely
- Self-hosted runner risks
- Workflow_dispatch inputs used unsafely
- Missing environment protections for deployment workflows"""


class WorkflowAnalyzerModule(BaseModule):
    MODULE_ID = "M5"
    MODULE_NAME = "GitHub Actions Workflow Analyzer"
    DESCRIPTION = "Analyses GitHub Actions workflow YAML files for security risks and misconfigurations."

    def run(self, context: dict[str, Any], query: Optional[str] = None) -> str:
        org = context.get("org", "unknown")
        workflows = context.get("workflows")

        if not workflows:
            return (
                "No workflow data available. Workflow analysis requires fetching "
                "workflow files first.\n\n"
                "Use `/workflow <owner/repo>` to analyse workflows for a specific repository, "
                "or `/workflow` to scan the current target."
            )

        # Build the prompt with all workflow content
        workflow_blocks = []
        for wf in workflows:
            repo = wf.get("repo", "unknown")
            filename = wf.get("filename", "unknown")
            content = wf.get("content", "")
            if content:
                workflow_blocks.append(
                    f"--- WORKFLOW: {repo}/.github/workflows/{filename} ---\n{content}"
                )

        if not workflow_blocks:
            return "Workflow files were found but had no readable content."

        prompt = f"""Analyse the following GitHub Actions workflow files for security risks.
Organisation: {org}

{chr(10).join(workflow_blocks)}

{f"USER QUESTION: {query}" if query else ""}

Produce a Workflow Security Analysis Report:

1. **RISK SUMMARY** — Overall risk level for CI/CD pipeline security (Critical / High / Medium / Low)
2. **FINDINGS** — For each issue found:
   - Workflow file and line context
   - Risk severity (Critical / High / Medium / Low)
   - Description of the vulnerability
   - Potential attack scenario
   - **Fix**: Corrected YAML snippet
3. **SECURE PRACTICES ALREADY IN PLACE** — Acknowledge any good security patterns found
4. **RECOMMENDATIONS** — Top prioritised actions to harden the CI/CD pipeline

Analyse every workflow thoroughly. If no issues are found, confirm the workflows follow security best practices."""

        logger.debug("M5 Workflow Analyzer: analysing %d workflows", len(workflows))
        response = self._llm.complete(prompt, system=SYSTEM_PROMPT, max_tokens=2500)
        return response.text
