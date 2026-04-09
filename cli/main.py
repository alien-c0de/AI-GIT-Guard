"""
cli/main.py — AI Git Guard unified interactive AI terminal.
Entry point: `python main.py` or `python main.py --org my-org`

Starts a single interactive AI session that connects to GitHub Advanced
Security and your configured LLM. Type anything in plain English and the
AI will automatically route your request to the right analysis module.

Slash commands for power users:
  /triage          — Run alert triage & prioritization
  /remediate       — Get fix/upgrade commands
  /narrate         — Generate executive briefing
  /report <fmt>    — Export report (pdf, html, excel)
  /fetch           — Refresh alerts from GitHub
  /help            — Show available commands
  /exit            — Quit
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.markdown import Markdown
from rich import print as rprint

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

console = Console()
logger = logging.getLogger(__name__)


# ── Slash-command autocomplete ────────────────────────────────────────────────

#: Full list of slash commands shown in the completion dropdown.
_SLASH_COMMANDS: list[tuple[str, str]] = [
    ("/triage",             "Prioritised alert ranking"),
    ("/remediate",          "Fix & upgrade guidance"),
    ("/risk",               "Risk prediction & trend analysis"),
    ("/workflow",           "Analyse GitHub Actions workflows"),
    ("/narrate",            "Executive security briefing"),
    ("/report pdf",         "Export PDF report"),
    ("/report html",        "Export HTML dashboard"),
    ("/report excel",       "Export Excel workbook"),
    ("/report weekly",      "Weekly org security report (Excel)"),
    ("/report enterprise",  "Enterprise multi-org inventory (Excel)"),
    ("/fetch",              "Refresh alerts from GitHub"),
    ("/clear",              "Clear the terminal screen"),
    ("/help",               "Show all commands"),
    ("/exit",               "Quit AI Git Guard"),
]


class SlashCommandCompleter(Completer):
    """
    Activates only when the input starts with '/'.
    Filters the command list as the user types, and shows
    the command description as inline metadata.
    """

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        typed_lower = text.lower()
        for cmd, desc in _SLASH_COMMANDS:
            if cmd.startswith(typed_lower):
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display=cmd,
                    display_meta=desc,
                )


_PT_STYLE = Style.from_dict({
    # dropdown background / text
    "completion-menu.completion":                  "bg:#0d2137 #c8d8e8",
    # currently highlighted entry
    "completion-menu.completion.current":          "bg:#0078d4 #ffffff bold",
    # description column
    "completion-menu.meta.completion":             "bg:#0a1a2e #7aa3c8",
    "completion-menu.meta.completion.current":     "bg:#005fa3 #ddeeff",
    # scrollbar
    "scrollbar.background":                        "bg:#0d2137",
    "scrollbar.button":                            "bg:#0078d4",
})


def _create_prompt_session() -> PromptSession:
    """Build the prompt_toolkit session used in the interactive loop."""
    # On Windows, enable Virtual Terminal Processing so ANSI colours render
    # correctly in cmd.exe / older consoles. No-op on Windows Terminal / PS7.
    import sys
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass  # Non-fatal — colours may be plain but autocomplete still works

    return PromptSession(
        completer=SlashCommandCompleter(),
        complete_while_typing=True,       # dropdown appears as you type
        auto_suggest=AutoSuggestFromHistory(),  # grey ghost text for previous queries
        history=InMemoryHistory(),
        style=_PT_STYLE,
        reserve_space_for_menu=6,         # lines reserved for the dropdown
    )




def _banner() -> None:
    console.print()
    console.print(Panel.fit(
        "[bold cyan]AI Git Guard[/bold cyan]\n"
        "[white]GitHub Advanced Security — Interactive AI Terminal[/white]\n"
        "[dim]v0.2.0 • Dependabot • Code Scanning • Secret Scanning[/dim]",
        border_style="cyan",
        padding=(1, 4),
    ))
    console.print()


def _load_context(org: Optional[str] = None, repo: Optional[str] = None, state: str = "open") -> dict:
    """Fetch alerts and build the context dict used by all modules."""
    from config import settings
    from github.client import GitHubClient
    from github.aggregator import (
        parse_dependabot_alert, parse_code_scanning_alert,
        parse_secret_scanning_alert, build_summary
    )
    from github.cache import AlertCache

    target_org = org or settings.GITHUB_ORG

    with AlertCache() as cache, GitHubClient() as gh:
        # ── Dependabot ──────────────────────────────────────────────────────
        cache_key_dep = f"dep:{target_org}:{repo}:{state}"
        raw_dep = cache.get(cache_key_dep)
        if raw_dep is None:
            try:
                with console.status("[cyan]  │ Dependabot alerts…[/cyan]"):
                    if repo:
                        owner, repo_name = repo.split("/", 1)
                        raw_dep = gh.get_repo_dependabot_alerts(owner, repo_name, state)
                    else:
                        raw_dep = gh.get_org_dependabot_alerts(target_org, state)
                cache.set(cache_key_dep, raw_dep)
                console.print(f"  [green]✓[/green] Dependabot alerts      [dim]({len(raw_dep)} fetched)[/dim]")
            except Exception as exc:
                logger.warning("Failed to fetch Dependabot alerts: %s", exc)
                console.print(f"  [yellow]⚠[/yellow] Dependabot alerts      [dim](failed: {exc})[/dim]")
                raw_dep = []
        else:
            console.print(f"  [green]✓[/green] Dependabot alerts      [dim]({len(raw_dep)} cached)[/dim]")
        dep_alerts = [parse_dependabot_alert(r) for r in raw_dep]

        # ── Code Scanning ───────────────────────────────────────────────────
        cache_key_cs = f"cs:{target_org}:{repo}:{state}"
        raw_cs = cache.get(cache_key_cs)
        if raw_cs is None:
            try:
                with console.status("[cyan]  │ Code Scanning alerts…[/cyan]"):
                    if repo:
                        owner, repo_name = repo.split("/", 1)
                        raw_cs = gh.get_repo_code_scanning_alerts(owner, repo_name, state)
                    else:
                        raw_cs = gh.get_org_code_scanning_alerts(target_org, state)
                cache.set(cache_key_cs, raw_cs)
                console.print(f"  [green]✓[/green] Code Scanning alerts   [dim]({len(raw_cs)} fetched)[/dim]")
            except Exception as exc:
                logger.warning("Failed to fetch Code Scanning alerts: %s", exc)
                console.print(f"  [yellow]⚠[/yellow] Code Scanning alerts   [dim](failed: {exc})[/dim]")
                raw_cs = []
        else:
            console.print(f"  [green]✓[/green] Code Scanning alerts   [dim]({len(raw_cs)} cached)[/dim]")
        cs_alerts = [parse_code_scanning_alert(r) for r in raw_cs]

        # ── Secret Scanning ─────────────────────────────────────────────────
        cache_key_ss = f"ss:{target_org}:{repo}:{state}"
        raw_ss = cache.get(cache_key_ss)
        if raw_ss is None:
            try:
                with console.status("[cyan]  │ Secret Scanning alerts…[/cyan]"):
                    if repo:
                        owner, repo_name = repo.split("/", 1)
                        raw_ss = gh.get_repo_secret_scanning_alerts(owner, repo_name, state)
                    else:
                        raw_ss = gh.get_org_secret_scanning_alerts(target_org, state)
                cache.set(cache_key_ss, raw_ss)
                console.print(f"  [green]✓[/green] Secret Scanning alerts [dim]({len(raw_ss)} fetched)[/dim]")
            except Exception as exc:
                logger.warning("Failed to fetch Secret Scanning alerts: %s", exc)
                console.print(f"  [yellow]⚠[/yellow] Secret Scanning alerts [dim](failed: {exc})[/dim]")
                raw_ss = []
        else:
            console.print(f"  [green]✓[/green] Secret Scanning alerts [dim]({len(raw_ss)} cached)[/dim]")
        ss_alerts = [parse_secret_scanning_alert(r) for r in raw_ss]

    summary = build_summary(target_org, dep_alerts, cs_alerts, ss_alerts)
    return {
        "org": target_org,
        "repo": repo,
        "dependabot": dep_alerts,
        "code_scanning": cs_alerts,
        "secret_scanning": ss_alerts,
        "summary": summary,
    }


def _print_summary_table(ctx: dict) -> None:
    s = ctx["summary"]
    table = Table(title=f"Alert Summary -- {ctx['org']}", show_header=True, header_style="bold cyan")
    table.add_column("Category", style="bold")
    table.add_column("Total", justify="right")
    table.add_column("Open", justify="right", style="yellow")
    table.add_column("Critical", justify="right", style="red")
    table.add_column("High", justify="right", style="orange3")

    table.add_row("Dependabot",       str(s.total_dependabot),     str(s.open_dependabot),     str(s.critical_dependabot), str(s.high_dependabot))
    table.add_row("Code Scanning",    str(s.total_code_scanning),  str(s.open_code_scanning),  str(s.critical_code_scanning), str(s.high_code_scanning))
    table.add_row("Secret Scanning",  str(s.total_secret_scanning), str(s.open_secret_scanning), "N/A", "N/A")
    console.print(table)
    if s.push_protection_bypassed:
        console.print(f"[red bold]WARNING: {s.push_protection_bypassed} push protection bypass(es) detected![/red bold]")


def _print_help() -> None:
    """Print the help panel showing available commands."""
    help_text = """[bold]Natural Language[/bold] — Just type your question in plain English:
  [dim]"What are my top risks?"[/dim]
  [dim]"Show me critical Dependabot alerts"[/dim]
  [dim]"Generate a PDF executive report"[/dim]
  [dim]"Generate a compliance audit HTML report"[/dim]
  [dim]"Predict which repos are most at risk"[/dim]
  [dim]"Analyse my GitHub Actions workflows for security issues"[/dim]
  [dim]"How do I fix the lodash vulnerability?"[/dim]

[bold]Slash Commands[/bold] (shortcuts):
  [cyan]/triage[/cyan]              Prioritised alert ranking
  [cyan]/remediate[/cyan]           Fix & upgrade guidance
  [cyan]/risk[/cyan]                Risk prediction & trend analysis
  [cyan]/workflow[/cyan] <repo>     Analyse GitHub Actions workflows
  [cyan]/narrate[/cyan]             Executive security briefing
  [cyan]/report[/cyan] <format>     Export report (pdf, html, excel)
  [cyan]/report weekly[/cyan]       Weekly org security report (Excel)
  [cyan]/report enterprise[/cyan]   Enterprise multi-org inventory (Excel, requires --list-orgs)
  [cyan]/fetch[/cyan]               Refresh alerts from GitHub
  [cyan]/clear[/cyan]               Clear the terminal screen
  [cyan]/help[/cyan]                Show this help
  [cyan]/exit[/cyan]                Quit

[bold]Report Templates[/bold]:
  [yellow]executive[/yellow]     KPIs + AI analysis only — for leadership
  [yellow]technical[/yellow]     Full detail with all alert tables
  [yellow]compliance[/yellow]    Formal audit report with sign-off block
  [dim]Tip: say "generate executive PDF report" or use /report to pick interactively[/dim]"""
    console.print(Panel(help_text, title="[bold green]Available Commands[/bold green]", border_style="green"))


def _report_header(title: str, ctx: dict) -> str:
    """Build a professional header block with tool name, org details, and timestamp."""
    from datetime import datetime, timezone
    org = ctx.get("org", "N/A")
    repo = ctx.get("repo", "")
    ts = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    scope = f"Repository: {repo}" if repo else f"Organisation: {org}"
    header = (
        f"[bold cyan]AI Git Guard[/bold cyan] — GitHub Advanced Security AI Agent\n"
        f"[dim]{scope}  |  {ts}[/dim]\n"
        f"[dim]{'─' * 60}[/dim]"
    )
    return header


def _render_ai_panel(result: str, panel_title: str, ctx: dict) -> None:
    """
    Render header + AI result together inside a single Rich Panel.

    Header and LLM content are combined into one Markdown string so that
    everything appears inside a single panel box.  Using Markdown directly
    as the Panel renderable avoids the Group/width-propagation bug that
    causes content to appear outside or not at all on Windows.
    """
    from datetime import datetime, timezone
    org = ctx.get("org", "N/A")
    repo = ctx.get("repo", "")
    ts = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    scope = f"Repository: {repo}" if repo else f"Organisation: {org}"

    header_md = (
        f"**AI Git Guard** \u2014 GitHub Advanced Security AI Agent  \n"
        f"*{scope}  |  {ts}*\n\n"
        f"{'\u2500' * 60}\n\n"
    )

    content = (result or "").strip()
    if content:
        full_md = header_md + content
    else:
        full_md = (
            header_md
            + "> \u26a0\ufe0f  **The AI did not return any content.**  \n"
            + "> Check your LLM connection and try again."
        )

    console.print(Panel(
        Markdown(full_md),
        title=panel_title,
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print()


def _prompt_save_report(result: str, title: str, ctx: dict) -> None:
    """Ask the user if they want to save the displayed analysis as a PDF report."""
    from output.renderer import render
    console.print()
    save = Prompt.ask(
        "[bold cyan]Would you like to download this report as PDF?[/bold cyan]",
        choices=["yes", "no", "y", "n"],
        default="no",
    ).lower()
    if save in ("yes", "y"):
        template = _pick_report_template()
        with console.status("[cyan]Generating PDF report…[/cyan]"):
            path = render(result, title=title, fmt="pdf", context=ctx, template=template)
        console.print(f"[green]✓ Report saved: {path}[/green]")


def _handle_triage(llm, ctx: dict, output_fmt: str = "text", template: str = "technical") -> None:
    """Run M1 Triage and display/save result."""
    from modules.m1_triage import TriageModule
    from output.renderer import render

    with console.status("[cyan]AI is analysing and triaging alerts…[/cyan]"):
        result = TriageModule(llm).run(ctx)

    formatted = render(result, title="AI Git Guard — Alert Triage Report", fmt=output_fmt, context=ctx, template=template)
    if output_fmt == "text":
        _render_ai_panel(result, "[bold cyan]Alert Triage Report[/bold cyan]", ctx)
        _prompt_save_report(result, "AI Git Guard — Alert Triage Report", ctx)
    else:
        console.print(f"[green]✓ Report saved: {formatted}[/green]")


def _handle_remediation(llm, ctx: dict, output_fmt: str = "text", template: str = "technical") -> None:
    """Run M2 Remediation and display/save result."""
    from modules.m2_remediation import RemediationModule
    from output.renderer import render

    with console.status("[cyan]Generating remediation guidance…[/cyan]"):
        result = RemediationModule(llm).run(ctx)

    formatted = render(result, title="AI Git Guard — Remediation Guidance", fmt=output_fmt, context=ctx, template=template)
    if output_fmt == "text":
        _render_ai_panel(result, "[bold cyan]Remediation Guidance[/bold cyan]", ctx)
        _prompt_save_report(result, "AI Git Guard — Remediation Guidance", ctx)
    else:
        console.print(f"[green]✓ Report saved: {formatted}[/green]")


def _handle_narrate(llm, ctx: dict, output_fmt: str = "text", template: str = "technical") -> None:
    """Run M6 Narrator and display/save result."""
    from modules.m6_narrator import NarratorModule
    from output.renderer import render

    with console.status("[cyan]Generating executive security narrative…[/cyan]"):
        result = NarratorModule(llm).run(ctx)

    formatted = render(result, title="AI Git Guard — Security Posture Briefing", fmt=output_fmt, context=ctx, template=template)
    if output_fmt == "text":
        _render_ai_panel(result, "[bold cyan]Executive Security Briefing[/bold cyan]", ctx)
        _prompt_save_report(result, "AI Git Guard — Security Posture Briefing", ctx)
    else:
        console.print(f"[green]✓ Report saved: {formatted}[/green]")


def _handle_risk_prediction(llm, ctx: dict, output_fmt: str = "text", template: str = "technical") -> None:
    """Run M4 Risk Prediction and display/save result."""
    from modules.m4_risk_prediction import RiskPredictionModule
    from output.renderer import render

    with console.status("[cyan]AI is analysing risk patterns and predicting threats…[/cyan]"):
        result = RiskPredictionModule(llm).run(ctx)

    formatted = render(result, title="AI Git Guard — Risk Prediction Report", fmt=output_fmt, context=ctx, template=template)
    if output_fmt == "text":
        _render_ai_panel(result, "[bold cyan]Risk Prediction Report[/bold cyan]", ctx)
        _prompt_save_report(result, "AI Git Guard — Risk Prediction Report", ctx)
    else:
        console.print(f"[green]✓ Report saved: {formatted}[/green]")


def _handle_workflow_analysis(llm, ctx: dict, args: str = "") -> None:
    """Run M5 Workflow Analyzer: fetch workflows then analyse."""
    from github.client import GitHubClient
    from modules.m5_workflow_analyzer import WorkflowAnalyzerModule

    # Determine target repo(s)
    target_repo = args.strip() if args.strip() else ctx.get("repo")
    org = ctx.get("org", "")

    if not target_repo:
        # No specific repo — scan repos from alert data to find workflows
        alert_repos: set[str] = set()
        for alert_type in ("dependabot", "code_scanning", "secret_scanning"):
            for a in ctx.get(alert_type, []):
                alert_repos.add(a.repository.full_name)

        if not alert_repos:
            console.print("[yellow]No repositories found in alert data. "
                          "Specify a repo: /workflow owner/repo[/yellow]")
            return

        # Limit to top 5 repos to keep analysis manageable
        target_repos = sorted(alert_repos)[:5]
        console.print(f"[dim]Scanning workflows in {len(target_repos)} repositories…[/dim]")
    else:
        target_repos = [target_repo if "/" in target_repo else f"{org}/{target_repo}"]

    workflows: list[dict] = []
    with GitHubClient() as gh:
        for repo_full in target_repos:
            parts = repo_full.split("/", 1)
            if len(parts) != 2:
                continue
            owner, repo_name = parts

            with console.status(f"[cyan]Fetching workflows for {repo_full}…[/cyan]"):
                wf_files = gh.list_repo_workflows(owner, repo_name)

            if not wf_files:
                console.print(f"  [dim]No workflows found in {repo_full}[/dim]")
                continue

            for wf in wf_files:
                filename = wf.get("name", "")
                path = wf.get("path", f".github/workflows/{filename}")
                with console.status(f"[cyan]  Reading {filename}…[/cyan]"):
                    content = gh.get_file_content(owner, repo_name, path)
                if content:
                    workflows.append({
                        "repo": repo_full,
                        "filename": filename,
                        "content": content,
                    })
                    console.print(f"  [green]✓[/green] {repo_full}/{filename}")

    if not workflows:
        console.print("[yellow]No workflow files found in the scanned repositories.[/yellow]")
        return

    console.print(f"[dim]Analysing {len(workflows)} workflow file(s)…[/dim]")

    # Inject workflows into context for the module
    analysis_ctx = {**ctx, "workflows": workflows}

    with console.status("[cyan]AI is analysing workflow security…[/cyan]"):
        result = WorkflowAnalyzerModule(llm).run(analysis_ctx)

    header = _report_header("Workflow Security Analysis", ctx)
    console.print(Panel(
        f"{header}\n\n{result}",
        title="[bold cyan]Workflow Security Analysis[/bold cyan]",
        border_style="cyan",
    ))
    _prompt_save_report(result, "AI Git Guard — Workflow Security Analysis", ctx)


def _handle_query(query_module, ctx: dict, query: str) -> None:
    """Run M3 Query and display result."""
    with console.status("[cyan]Thinking…[/cyan]"):
        result = query_module.run(ctx, query=query)

    console.print(Panel(result, title="[bold green]AI Git Guard[/bold green]", border_style="green"))


def _handle_weekly_report(ctx: dict, repos: list[dict] | None = None) -> None:
    """Generate Weekly Organisation Excel Report."""
    from output.excel_reports import render_weekly_report
    from github.client import GitHubClient

    org = ctx.get("org") or ""

    if repos is None:
        with console.status(f"[cyan]Fetching repository list for {org}…[/cyan]"):
            with GitHubClient() as gh:
                repos = gh.list_repos(org)
        console.print(f"  [green]✓[/green] Fetched {len(repos)} repositories")

    with console.status("[cyan]Generating Weekly Organisation Report…[/cyan]"):
        path = render_weekly_report(ctx, repos)

    console.print(f"[green]✓ Weekly Report saved: {path}[/green]")


def _handle_enterprise_report(user_orgs: list[dict]) -> None:
    """Generate Enterprise Repository Inventory Excel Report (multi-org)."""
    from output.excel_reports import render_enterprise_report
    from github.client import GitHubClient
    from github.aggregator import (
        parse_dependabot_alert, parse_code_scanning_alert,
        parse_secret_scanning_alert, build_summary,
    )
    from github.cache import AlertCache

    all_org_data: list[dict] = []

    with AlertCache() as cache, GitHubClient() as gh:
        for i, org_dict in enumerate(user_orgs, 1):
            org_name = org_dict.get("login", "unknown")
            console.print(f"  [dim]({i}/{len(user_orgs)})[/dim] Processing [bold]{org_name}[/bold]…")

            # Fetch repos
            with console.status(f"[cyan]    Fetching repos for {org_name}…[/cyan]"):
                try:
                    repos = gh.list_repos(org_name)
                except Exception:
                    console.print(f"    [yellow]⚠ Could not fetch repos for {org_name}[/yellow]")
                    repos = []

            # Fetch alerts (with caching)
            dep_alerts = cs_alerts = ss_alerts = []
            try:
                cache_key_dep = f"dep:{org_name}:None:open"
                raw_dep = cache.get(cache_key_dep)
                if raw_dep is None:
                    raw_dep = gh.get_org_dependabot_alerts(org_name, "open")
                    cache.set(cache_key_dep, raw_dep)
                dep_alerts = [parse_dependabot_alert(r) for r in raw_dep]
            except Exception as exc:
                logger.warning("Failed to fetch Dependabot alerts for %s: %s", org_name, exc)

            try:
                cache_key_cs = f"cs:{org_name}:None:open"
                raw_cs = cache.get(cache_key_cs)
                if raw_cs is None:
                    raw_cs = gh.get_org_code_scanning_alerts(org_name, "open")
                    cache.set(cache_key_cs, raw_cs)
                cs_alerts = [parse_code_scanning_alert(r) for r in raw_cs]
            except Exception as exc:
                logger.warning("Failed to fetch Code Scanning alerts for %s: %s", org_name, exc)

            try:
                cache_key_ss = f"ss:{org_name}:None:open"
                raw_ss = cache.get(cache_key_ss)
                if raw_ss is None:
                    raw_ss = gh.get_org_secret_scanning_alerts(org_name, "open")
                    cache.set(cache_key_ss, raw_ss)
                ss_alerts = [parse_secret_scanning_alert(r) for r in raw_ss]
            except Exception as exc:
                logger.warning("Failed to fetch Secret Scanning alerts for %s: %s", org_name, exc)

            summary = build_summary(org_name, dep_alerts, cs_alerts, ss_alerts)

            all_org_data.append({
                "org": org_name,
                "repos": repos,
                "dependabot": dep_alerts,
                "code_scanning": cs_alerts,
                "secret_scanning": ss_alerts,
                "summary": summary,
            })
            console.print(f"    [green]✓[/green] {org_name}: {len(repos)} repos, "
                          f"{len(dep_alerts)} dep, {len(cs_alerts)} cs, {len(ss_alerts)} ss alerts")

    with console.status("[cyan]Generating Enterprise Repository Inventory…[/cyan]"):
        path = render_enterprise_report(all_org_data)

    console.print(f"[green]✓ Enterprise Report saved: {path}[/green]")


def _detect_report_type(user_input: str) -> str:
    """Detect what type of report content the user wants."""
    lower = user_input.lower()
    if any(w in lower for w in ("triage", "prioriti", "rank", "top risk")):
        return "triage"
    if any(w in lower for w in ("remediat", "fix", "patch", "upgrade")):
        return "remediation"
    if any(w in lower for w in ("risk predict", "risk assess", "risk score", "proactive", "predict")):
        return "risk"
    return "narrate"


def _pick_output_format() -> str:
    """Interactive format picker."""
    console.print()
    console.print("[bold cyan]Select report format:[/bold cyan]")
    formats = [
        ("1", "PDF",   "Professional PDF document"),
        ("2", "HTML",  "Interactive HTML dashboard"),
        ("3", "Excel", "Multi-sheet Excel workbook"),
    ]
    for num, name, desc in formats:
        console.print(f"  [bold]{num}[/bold]. {name}  [dim]— {desc}[/dim]")
    console.print()
    choice = Prompt.ask("[bold cyan]Format[/bold cyan]", choices=["1", "2", "3"], default="1")
    return {"1": "pdf", "2": "html", "3": "excel"}[choice]


def _pick_report_template() -> str:
    """Interactive template picker."""
    from output.renderer import TEMPLATES
    console.print()
    console.print("[bold cyan]Select report template:[/bold cyan]")
    template_keys = list(TEMPLATES.keys())
    for idx, key in enumerate(template_keys, 1):
        t = TEMPLATES[key]
        console.print(f"  [bold]{idx}[/bold]. {t['label']}  [dim]— {t['description']}[/dim]")
    console.print()
    choice = Prompt.ask("[bold cyan]Template[/bold cyan]",
                        choices=[str(i) for i in range(1, len(template_keys) + 1)], default="1")
    return template_keys[int(choice) - 1]


def _detect_template(user_input: str) -> str | None:
    """Detect template name from natural language."""
    lower = user_input.lower()
    if any(w in lower for w in ("executive", "summary", "leadership", "management", "c-suite")):
        return "executive"
    if any(w in lower for w in ("technical", "detail", "engineer", "full")):
        return "technical"
    if any(w in lower for w in ("compliance", "audit", "formal", "regulation")):
        return "compliance"
    return None


def _handle_report(llm, ctx: dict, args: str) -> None:
    """Generate a report in the specified format and template."""
    from modules.m1_triage import TriageModule
    from modules.m2_remediation import RemediationModule
    from modules.m4_risk_prediction import RiskPredictionModule
    from modules.m6_narrator import NarratorModule
    from output.renderer import render

    # Extract format from args — works for both "/report excel" and natural language
    fmt = _detect_output_format(args)
    template = _detect_template(args)

    # If neither format nor template specified, show interactive pickers
    if fmt == "text" and template is None:
        fmt = _pick_output_format()
        template = _pick_report_template()
    else:
        if fmt == "text":
            fmt = _pick_output_format()
        if template is None:
            template = _pick_report_template()

    # Detect report content type from the user's message
    report_type = _detect_report_type(args)
    module_map = {
        "triage": (TriageModule, "Alert Triage Report"),
        "remediation": (RemediationModule, "Remediation Guidance"),
        "risk": (RiskPredictionModule, "Risk Prediction Report"),
        "narrate": (NarratorModule, "Security Posture Briefing"),
    }
    ModuleClass, title = module_map[report_type]

    console.print(f"[dim]Format: {fmt.upper()} | Template: {template.title()} | Content: {report_type.title()}[/dim]")

    with console.status(f"[cyan]Generating {fmt.upper()} {title} ({template.title()})…[/cyan]"):
        result = ModuleClass(llm).run(ctx)

    path = render(result, title=f"AI Git Guard — {title}", fmt=fmt, context=ctx, template=template)
    console.print(f"[green]✓ Report saved: {path}[/green]")


def _detect_output_format(user_input: str) -> str:
    """Check if user mentions a specific output format in their message."""
    lower = user_input.lower()
    if "pdf" in lower:
        return "pdf"
    if "excel" in lower or "xlsx" in lower:
        return "excel"
    if "html" in lower:
        return "html"
    return "text"


# ── CLI Entry Point ───────────────────────────────────────────────────────────

@click.command()
@click.option("--org",       default=None, help="GitHub organisation (overrides .env GITHUB_ORG).")
@click.option("--repo",      default=None, help="Specific repo in owner/repo format.")
@click.option("--list-orgs", is_flag=True, help="Fetch and choose from all accessible organisations.")
@click.option("--debug",     is_flag=True, help="Enable debug logging.")
def cli(org: Optional[str], repo: Optional[str], list_orgs: bool, debug: bool) -> None:
    """AI Git Guard -- Interactive AI Security Terminal"""
    from config import settings
    from llm.factory import get_llm_adapter
    from modules.router import IntentRouter, Intent

    # ── Setup ──────────────────────────────────────────────────────────────
    settings.setup_logging()
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        # Restore verbose HTTP logs in debug mode
        for name in ("httpx", "httpcore", "urllib3", "github.client"):
            logging.getLogger(name).setLevel(logging.DEBUG)

    _banner()

    # ── Validate config ────────────────────────────────────────────────────
    try:
        settings.validate()
    except ValueError as e:
        console.print(f"[red bold]Configuration Error:[/red bold]\n{e}")
        console.print("[dim]Edit your .env file and try again.[/dim]")
        sys.exit(1)

    # ── Organisation selection ─────────────────────────────────────────────
    user_orgs: list[dict] = []  # stored for enterprise report generation
    if list_orgs and not org:
        from github.client import GitHubClient
        with console.status("[cyan]Fetching accessible organisations...[/cyan]"):
            try:
                from github.client import GitHubNetworkError, GitHubAPIError
                with GitHubClient() as gh:
                    user_orgs = gh.list_user_orgs()
            except GitHubNetworkError as e:
                logger.debug("Network error fetching organisations", exc_info=True)
                console.print(Panel(
                    f"[bold]Unable to reach the GitHub API.[/bold]\n\n"
                    f"{e}\n\n"
                    "[dim]Check your proxy settings or network access to [cyan]api.github.com[/cyan].[/dim]\n"
                    "Run with [bold]--debug[/bold] for full diagnostic output.",
                    title="[bold red]Network Connection Error[/bold red]",
                    border_style="red",
                ))
                sys.exit(1)
            except GitHubAPIError as e:
                logger.debug("GitHub API error fetching organisations", exc_info=True)
                console.print(Panel(
                    f"[bold]GitHub API returned an error.[/bold]\n\n"
                    f"Status [bold red]{e.status_code}[/bold red]: {e}\n\n"
                    "  • Verify [yellow]GITHUB_TOKEN[/yellow] is valid and has [cyan]read:org[/cyan] scope\n"
                    "  • Run with [bold]--debug[/bold] for full diagnostic output.",
                    title="[bold red]GitHub API Error[/bold red]",
                    border_style="red",
                ))
                sys.exit(1)
            except Exception as e:
                logger.debug("Unexpected error fetching organisations", exc_info=True)
                console.print(Panel(
                    f"[bold]Unexpected error fetching organisations.[/bold]\n\n"
                    f"{type(e).__name__}: {e}\n\n"
                    "Run with [bold]--debug[/bold] for the full diagnostic trace.",
                    title="[bold red]Unexpected Error[/bold red]",
                    border_style="red",
                ))
                sys.exit(1)

        if not user_orgs:
            console.print("[yellow]No organisations found for this token.[/yellow]")
            console.print("[dim]Falling back to GITHUB_ORG from .env...[/dim]")
        else:
            console.print()
            console.print("[bold cyan]Available organisations:[/bold cyan]")
            for idx, o in enumerate(user_orgs, 1):
                name = o.get("login", "unknown")
                desc = o.get("description", "") or ""
                desc_text = f"  [dim]-- {desc}[/dim]" if desc else ""
                console.print(f"  [bold]{idx}[/bold]. {name}{desc_text}")
            console.print()

            choice = Prompt.ask(
                "[bold cyan]Select organisation[/bold cyan]",
                choices=[str(i) for i in range(1, len(user_orgs) + 1)],
                default="1",
            )
            org = user_orgs[int(choice) - 1].get("login", "")
            console.print(f"[green]\u2713 Selected organisation:[/green] [bold]{org}[/bold]")

    # ── Detect & select LLM provider ──────────────────────────────────────
    with console.status("[cyan]Scanning for available LLM providers...[/cyan]"):
        available = settings.detect_available_providers()

    if not available:
        console.print("[red bold]No LLM providers detected.[/red bold]")
        console.print("[dim]Configure at least one provider in your .env file:[/dim]")
        console.print("[dim]  - OLLAMA_BASE_URL  (start Ollama server locally)[/dim]")
        console.print("[dim]  - ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN[/dim]")
        console.print("[dim]  - OPENAI_API_KEY[/dim]")
        console.print("[dim]  - COPILOT_TOKEN[/dim]")
        sys.exit(1)

    chosen_provider = None

    if len(available) == 1:
        # Only one provider available — auto-select
        chosen_provider = available[0]["id"]
        console.print(f"[green]✓ Auto-selected LLM:[/green] [bold]{available[0]['label']}[/bold]")
    else:
        # Multiple providers — ask the user to pick
        console.print()
        console.print("[bold cyan]Multiple LLM providers detected:[/bold cyan]")
        for idx, p in enumerate(available, 1):
            console.print(f"  [bold]{idx}[/bold]. {p['label']}")
        console.print()

        while chosen_provider is None:
            choice = Prompt.ask(
                "[bold cyan]Select provider[/bold cyan]",
                choices=[str(i) for i in range(1, len(available) + 1)],
                default="1",
            )
            chosen_provider = available[int(choice) - 1]["id"]

        console.print(f"[green]✓ Selected LLM:[/green] [bold]{available[int(choice) - 1]['label']}[/bold]")

    # Update settings so warn_cloud_llm and adapters use the chosen provider
    settings.LLM_PROVIDER = chosen_provider
    settings.warn_cloud_llm(console=console)

    # ── Connect to LLM ────────────────────────────────────────────────────
    with console.status("[cyan]Connecting to AI...[/cyan]"):
        try:
            llm = get_llm_adapter(chosen_provider)
        except Exception as e:
            console.print(f"[red bold]Failed to connect to LLM:[/red bold] {e}")
            sys.exit(1)

    console.print(f"[green]✓ Connected to AI:[/green] [bold]{llm.provider_name}[/bold]")

    # ── Fetch alert data ───────────────────────────────────────────────────
    from github.client import GitHubNetworkError, GitHubAPIError
    target = repo or org or settings.GITHUB_ORG
    console.print(f"[dim]Fetching security alerts for [bold]{target}[/bold]…[/dim]")
    try:
        ctx = _load_context(org, repo)
    except GitHubNetworkError as e:
        logger.debug("Network error fetching alerts", exc_info=True)
        console.print(Panel(
            f"[bold]Unable to reach the GitHub API.[/bold]\n\n"
            f"{e}\n\n"
            "[dim]Possible causes:[/dim]\n"
            "  • Corporate firewall blocking outbound HTTPS to [cyan]api.github.com[/cyan]\n"
            "  • Missing or incorrect proxy settings\n"
            "  • No internet access in this environment\n\n"
            "[dim]Actions to try:[/dim]\n"
            "  1. Set [yellow]HTTPS_PROXY=http://proxy-host:port[/yellow] in your [bold].env[/bold] file\n"
            "  2. Ask your network team to allow [cyan]api.github.com:443[/cyan]\n"
            "  3. Run with [bold]--debug[/bold] for full diagnostic output",
            title="[bold red]Network Connection Error[/bold red]",
            border_style="red",
        ))
        sys.exit(1)
    except GitHubAPIError as e:
        logger.debug("GitHub API error fetching alerts", exc_info=True)
        console.print(Panel(
            f"[bold]GitHub API returned an error.[/bold]\n\n"
            f"Status [bold red]{e.status_code}[/bold red]: {e}\n\n"
            "[dim]Actions to try:[/dim]\n"
            "  • Verify [yellow]GITHUB_TOKEN[/yellow] is set and not expired in your [bold].env[/bold] file\n"
            "  • Confirm the token has [cyan]security_events[/cyan] and [cyan]read:org[/cyan] scopes\n"
            "  • Check [yellow]GITHUB_ORG[/yellow] is the correct organisation name\n"
            "  • Run with [bold]--debug[/bold] for full diagnostic output",
            title="[bold red]GitHub API Error[/bold red]",
            border_style="red",
        ))
        sys.exit(1)
    except Exception as e:
        logger.debug("Unexpected error fetching alerts", exc_info=True)
        console.print(Panel(
            f"[bold]An unexpected error occurred while fetching alert data.[/bold]\n\n"
            f"{type(e).__name__}: {e}\n\n"
            "Run with [bold]--debug[/bold] for the full diagnostic trace.",
            title="[bold red]Unexpected Error[/bold red]",
            border_style="red",
        ))
        sys.exit(1)

    console.print(f"[green]✓ Alerts loaded successfully[/green]")
    console.print()
    _print_summary_table(ctx)

    # Pre-fetch repo list (used by weekly report; cached in session)
    _cached_repos: list[dict] | None = None

    # ── Initialize router and query module ───────────────────────────────
    router = IntentRouter(llm)

    from modules.m3_query import NLQueryModule
    query_module = NLQueryModule(llm)

    # ── Interactive loop ───────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        "[bold green]AI Git Guard Terminal[/bold green] — Ready\n"
        "[dim]Ask anything about your security alerts in plain English.\n"
        "The AI will automatically analyse, triage, or generate reports.\n"
        "Type [bold]/[/bold] to browse commands with autocomplete, "
        "or [bold]/help[/bold] to list all commands.  "
        "[bold]/exit[/bold] to quit.[/dim]",
        border_style="green",
    ))

    _prompt_session = _create_prompt_session()
    # HTML-formatted prompt label — portable across Windows and Unix
    _PROMPT_LABEL = HTML("<ansibrightcyan><b>You</b></ansibrightcyan> <ansiwhite>›</ansiwhite> ")

    while True:
        try:
            user_input = _prompt_session.prompt(_PROMPT_LABEL).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        # ── Route the intent ───────────────────────────────────────────────
        intent, args = router.classify(user_input)

        # Professional routing indicator
        _INTENT_LABEL = {
            Intent.TRIAGE:          ("📊", "Alert Triage & Prioritization"),
            Intent.REMEDIATION:     ("🔧", "Remediation Guidance"),
            Intent.RISK_PREDICTION: ("🔮", "Risk Prediction Engine"),
            Intent.WORKFLOW:        ("⚙️", "Workflow Security Analysis"),
            Intent.NARRATE:         ("📋", "Executive Briefing"),
            Intent.REPORT:          ("📄", "Report Generation"),
            Intent.QUERY:           ("💬", "AI Query Engine"),
            Intent.FETCH:           ("🔄", "Refreshing Data"),
        }
        if intent in _INTENT_LABEL:
            icon, label = _INTENT_LABEL[intent]
            console.print(f"  [dim]{icon} {label}[/dim]")

        try:
            if intent == Intent.EXIT:
                console.print("[dim]Goodbye! Stay secure.[/dim]")
                break

            elif intent == Intent.HELP:
                _print_help()

            elif intent == Intent.CLEAR:
                click.clear()
                _banner()
                _print_summary_table(ctx)

            elif intent == Intent.FETCH:
                console.print("[dim]Refreshing alert data from GitHub…[/dim]")
                ctx = _load_context(org, repo)
                _print_summary_table(ctx)
                console.print("[green]✓ Alert data refreshed.[/green]")

            elif intent == Intent.TRIAGE:
                output_fmt = _detect_output_format(args)
                _handle_triage(llm, ctx, output_fmt)

            elif intent == Intent.REMEDIATION:
                output_fmt = _detect_output_format(args)
                _handle_remediation(llm, ctx, output_fmt)

            elif intent == Intent.NARRATE:
                output_fmt = _detect_output_format(args)
                _handle_narrate(llm, ctx, output_fmt)

            elif intent == Intent.RISK_PREDICTION:
                output_fmt = _detect_output_format(args)
                _handle_risk_prediction(llm, ctx, output_fmt)

            elif intent == Intent.WORKFLOW:
                _handle_workflow_analysis(llm, ctx, args)

            elif intent == Intent.REPORT:
                lower_args = args.lower()
                if "enterprise" in lower_args or "organization" in lower_args or "organisation" in lower_args or "inventory" in lower_args:
                    if user_orgs:
                        _handle_enterprise_report(user_orgs)
                    else:
                        console.print("[yellow]Enterprise report requires --list-orgs. "
                                      "Restart with: python main.py --list-orgs[/yellow]")
                elif "weekly" in lower_args or "week" in lower_args:
                    if _cached_repos is None:
                        from github.client import GitHubClient
                        target_org = ctx.get("org", "")
                        with console.status(f"[cyan]Fetching repository list for {target_org}…[/cyan]"):
                            with GitHubClient() as gh:
                                _cached_repos = gh.list_repos(target_org)
                        console.print(f"  [green]✓[/green] Fetched {len(_cached_repos)} repositories")
                    _handle_weekly_report(ctx, _cached_repos)
                else:
                    _handle_report(llm, ctx, args)

            elif intent == Intent.QUERY:
                lower_args = args.lower()
                if any(w in lower_args for w in ("enterprise", "inventory", "organization report", "organisation report")):
                    if user_orgs:
                        _handle_enterprise_report(user_orgs)
                    else:
                        console.print("[yellow]Enterprise report requires --list-orgs. "
                                      "Restart with: python main.py --list-orgs[/yellow]")
                elif any(w in lower_args for w in ("weekly report", "week report")):
                    if _cached_repos is None:
                        from github.client import GitHubClient
                        target_org = ctx.get("org", "")
                        with console.status(f"[cyan]Fetching repository list for {target_org}…[/cyan]"):
                            with GitHubClient() as gh:
                                _cached_repos = gh.list_repos(target_org)
                        console.print(f"  [green]✓[/green] Fetched {len(_cached_repos)} repositories")
                    _handle_weekly_report(ctx, _cached_repos)
                elif _detect_output_format(args) != "text":
                    _handle_report(llm, ctx, args)
                else:
                    _handle_query(query_module, ctx, args)

            else:
                _handle_query(query_module, ctx, user_input)

        except Exception as e:
            logger.exception("Error processing request")
            console.print(f"[red]Error: {e}[/red]")
            console.print("[dim]Try rephrasing your request, or type /help.[/dim]")


if __name__ == "__main__":
    cli()
