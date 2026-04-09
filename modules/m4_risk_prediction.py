"""
modules/m4_risk_prediction.py — Module 4: AI Risk Prediction Engine
Shifts from reactive to proactive security by identifying risk patterns
before they become incidents. Uses pattern-based heuristics (Phase 1) to
generate predictive risk scores per repository and organisation.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from modules.base import BaseModule
from models import AlertState, Severity

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior security risk analyst specialising in predictive threat modelling.
Your task is to analyse security alert patterns and repository characteristics to predict
which repositories and areas are most likely to experience new security incidents soon.
Be specific, data-driven, and actionable. Assign risk scores (Critical / High / Medium / Low)
and explain the reasoning behind each prediction.
Avoid speculation — base every prediction on the pattern data provided."""


class RiskPredictionModule(BaseModule):
    MODULE_ID = "M4"
    MODULE_NAME = "AI Risk Prediction Engine"
    DESCRIPTION = "Predicts security risks using pattern-based heuristics on alert trends and repo characteristics."

    def run(self, context: dict[str, Any], query: Optional[str] = None) -> str:
        org = context.get("org", "unknown")
        dep = context.get("dependabot", [])
        cs = context.get("code_scanning", [])
        ss = context.get("secret_scanning", [])
        summary = context.get("summary")

        # ── Gather heuristic signals ─────────────────────────────────────
        signals = self._compute_risk_signals(dep, cs, ss)

        # ── Build the prompt with pattern data ───────────────────────────
        prompt = f"""Analyse the following security alert patterns for GitHub organisation: {org}
Date: {datetime.now(timezone.utc).strftime('%B %d, %Y')}

=== ORGANISATION-LEVEL RISK SIGNALS ===
{self._format_org_signals(summary, dep, cs, ss)}

=== PER-REPOSITORY RISK PATTERNS ===
{signals['repo_risk_block']}

=== ALERT VELOCITY & TRENDS ===
{signals['velocity_block']}

=== SUPPLY CHAIN RISK INDICATORS ===
{signals['supply_chain_block']}

=== SCANNING COVERAGE GAPS ===
{signals['coverage_block']}

{f"USER QUESTION: {query}" if query else ""}

Based on the patterns above, produce a Risk Prediction Report:

1. **RISK SCORE SUMMARY** — Assign an overall risk level (Critical / High / Medium / Low) for the organisation
2. **TOP 5 AT-RISK REPOSITORIES** — Rank repos most likely to have new security incidents, with risk score and reasoning
3. **EMERGING THREAT PATTERNS** — Identify recurring vulnerability patterns that suggest systemic issues
4. **SUPPLY CHAIN RISK ASSESSMENT** — Evaluate dependency-related risks and vulnerable ecosystems
5. **PREDICTION: LIKELY NEXT INCIDENTS** — Based on trends, predict what types of incidents are most probable
6. **RECOMMENDED PREVENTIVE ACTIONS** — Concrete steps to reduce predicted risks before they materialise

Be data-driven and reference specific repos, packages, and alert patterns from the data above."""

        logger.debug("M4 Risk Prediction: analysing %d dep + %d cs + %d ss alerts",
                     len(dep), len(cs), len(ss))
        response = self._llm.complete(prompt, system=SYSTEM_PROMPT, max_tokens=2000)
        return response.text

    def _compute_risk_signals(self, dep: list, cs: list, ss: list) -> dict[str, str]:
        """Compute pattern-based heuristic signals from the alert data."""
        # ── Per-repo alert concentration ─────────────────────────────────
        repo_alert_counts: dict[str, dict[str, int]] = defaultdict(lambda: {
            "dependabot": 0, "code_scanning": 0, "secret_scanning": 0,
            "critical": 0, "high": 0, "open": 0,
        })

        for a in dep:
            repo = a.repository.name
            repo_alert_counts[repo]["dependabot"] += 1
            if a.state == AlertState.OPEN:
                repo_alert_counts[repo]["open"] += 1
            if a.severity == Severity.CRITICAL:
                repo_alert_counts[repo]["critical"] += 1
            elif a.severity == Severity.HIGH:
                repo_alert_counts[repo]["high"] += 1

        for a in cs:
            repo = a.repository.name
            repo_alert_counts[repo]["code_scanning"] += 1
            if a.state == AlertState.OPEN:
                repo_alert_counts[repo]["open"] += 1
            if a.severity == Severity.CRITICAL:
                repo_alert_counts[repo]["critical"] += 1
            elif a.severity == Severity.HIGH:
                repo_alert_counts[repo]["high"] += 1

        for a in ss:
            repo = a.repository.name
            repo_alert_counts[repo]["secret_scanning"] += 1
            if a.state == AlertState.OPEN:
                repo_alert_counts[repo]["open"] += 1
            repo_alert_counts[repo]["critical"] += 1  # secrets are always critical

        # Sort repos by total open+critical alerts (highest risk first)
        sorted_repos = sorted(
            repo_alert_counts.items(),
            key=lambda x: (x[1]["critical"] * 3 + x[1]["high"] * 2 + x[1]["open"]),
            reverse=True,
        )

        repo_lines = []
        for repo, counts in sorted_repos[:15]:
            risk_score = counts["critical"] * 3 + counts["high"] * 2 + counts["open"]
            repo_lines.append(
                f"- {repo}: dep={counts['dependabot']}, cs={counts['code_scanning']}, "
                f"ss={counts['secret_scanning']}, open={counts['open']}, "
                f"critical={counts['critical']}, high={counts['high']} "
                f"(risk_weight={risk_score})"
            )
        repo_risk_block = "\n".join(repo_lines) if repo_lines else "No repository-level data available."

        # ── Alert velocity (recent vs older) ─────────────────────────────
        now = datetime.now(timezone.utc)
        recent_cutoff = now - timedelta(days=30)
        older_cutoff = now - timedelta(days=90)

        recent_dep = sum(1 for a in dep if a.created_at and a.created_at > recent_cutoff)
        older_dep = sum(1 for a in dep if a.created_at and older_cutoff < a.created_at <= recent_cutoff)
        recent_cs = sum(1 for a in cs if a.created_at and a.created_at > recent_cutoff)
        older_cs = sum(1 for a in cs if a.created_at and older_cutoff < a.created_at <= recent_cutoff)

        velocity_block = (
            f"Dependabot: {recent_dep} alerts in last 30 days vs {older_dep} in previous 60 days "
            f"({'↑ INCREASING' if recent_dep > older_dep else '↓ decreasing' if recent_dep < older_dep else '→ stable'})\n"
            f"Code Scanning: {recent_cs} alerts in last 30 days vs {older_cs} in previous 60 days "
            f"({'↑ INCREASING' if recent_cs > older_cs else '↓ decreasing' if recent_cs < older_cs else '→ stable'})"
        )

        # ── Supply chain patterns ────────────────────────────────────────
        ecosystem_counts: Counter = Counter()
        vulnerable_packages: Counter = Counter()
        for a in dep:
            if a.state == AlertState.OPEN:
                ecosystem_counts[a.package.ecosystem] += 1
                vulnerable_packages[a.package.name] += 1

        supply_chain_lines = []
        if ecosystem_counts:
            supply_chain_lines.append("Vulnerable ecosystems:")
            for eco, count in ecosystem_counts.most_common(5):
                supply_chain_lines.append(f"  - {eco}: {count} open alerts")
        if vulnerable_packages:
            supply_chain_lines.append("Most frequently vulnerable packages:")
            for pkg, count in vulnerable_packages.most_common(10):
                supply_chain_lines.append(f"  - {pkg}: appears in {count} alerts")

        no_patch = sum(1 for a in dep if a.state == AlertState.OPEN and not a.patched_version)
        if no_patch:
            supply_chain_lines.append(f"Alerts with NO patched version available: {no_patch}")

        supply_chain_block = "\n".join(supply_chain_lines) if supply_chain_lines else "No supply chain data."

        # ── Scanning coverage gaps ───────────────────────────────────────
        repos_with_dep = {a.repository.name for a in dep}
        repos_with_cs = {a.repository.name for a in cs}
        repos_with_ss = {a.repository.name for a in ss}
        all_repos = repos_with_dep | repos_with_cs | repos_with_ss

        repos_no_cs = all_repos - repos_with_cs
        repos_no_dep = all_repos - repos_with_dep

        coverage_lines = [
            f"Total repos with any alerts: {len(all_repos)}",
            f"Repos with Dependabot alerts only (no code scanning): {len(repos_with_dep - repos_with_cs)}",
            f"Repos with code scanning alerts only (no Dependabot): {len(repos_with_cs - repos_with_dep)}",
        ]
        if repos_no_cs:
            coverage_lines.append(f"Repos without code scanning coverage: {', '.join(sorted(repos_no_cs)[:10])}")
        if repos_no_dep:
            coverage_lines.append(f"Repos without Dependabot coverage: {', '.join(sorted(repos_no_dep)[:10])}")

        coverage_block = "\n".join(coverage_lines)

        return {
            "repo_risk_block": repo_risk_block,
            "velocity_block": velocity_block,
            "supply_chain_block": supply_chain_block,
            "coverage_block": coverage_block,
        }

    def _format_org_signals(self, summary, dep: list, cs: list, ss: list) -> str:
        """Format organisation-level summary signals."""
        if not summary:
            return "No organisation summary available."

        open_total = summary.open_dependabot + summary.open_code_scanning + summary.open_secret_scanning
        critical_total = summary.critical_dependabot + summary.critical_code_scanning + summary.open_secret_scanning

        # Calculate fix rate (how many alerts have been resolved)
        fixed_dep = sum(1 for a in dep if a.state == AlertState.FIXED)
        dismissed_dep = sum(1 for a in dep if a.state == AlertState.DISMISSED)
        total_dep = len(dep)
        fix_rate_dep = f"{(fixed_dep / total_dep * 100):.0f}%" if total_dep else "N/A"

        public_repos_with_alerts = set()
        for a in dep + cs + ss:
            if not a.repository.private and a.state == AlertState.OPEN:
                public_repos_with_alerts.add(a.repository.name)

        lines = [
            f"Total open alerts across all types: {open_total}",
            f"Total critical/high severity: {critical_total}",
            f"Dependabot fix rate: {fix_rate_dep} ({fixed_dep} fixed, {dismissed_dep} dismissed out of {total_dep})",
            f"Push protection bypasses: {summary.push_protection_bypassed}",
            f"Repositories affected: {summary.repositories_affected}",
        ]
        if public_repos_with_alerts:
            lines.append(f"PUBLIC repos with open alerts (high exposure): {', '.join(sorted(public_repos_with_alerts)[:10])}")

        return "\n".join(lines)
