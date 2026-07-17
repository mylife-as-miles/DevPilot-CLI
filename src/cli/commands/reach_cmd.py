"""`devpilot reach` — optional internet research capability layer.

Provides safe, no-login channels natively and can bridge to Agent Reach
when installed.  Phase 1 does not implement cookie/login platforms.

Safety rules enforced:
  • Never uses shell=True
  • Never stores cookies
  • Never asks for social-media credentials
  • Never auto-installs system packages
  • Never modifies OpenClaw config
"""

from __future__ import annotations

import typer

from ...core.tools.reach import agent_reach_bridge
from ...core.tools.reach import doctor as reach_doctor
from ...core.tools.reach import providers as reach_providers
from ...core.tools.reach.channels import web as web_channel
from ...core.tools.reach.channels import search as search_channel
from ...core.tools.reach.channels import github as github_channel
from ...core.tools.reach.channels import youtube as youtube_channel
from ...core.tools.reach.channels import rss as rss_channel


# ── Top-level Reach group ────────────────────────────────────────────

reach_app = typer.Typer(
    name="reach",
    help=(
        "DevPilot Reach — optional internet research capability layer.\n\n"
        "Provides safe no-login channels natively and can bridge to\n"
        "Agent Reach when installed."
    ),
    no_args_is_help=True,
)


# ── Agent Reach sub-group ────────────────────────────────────────────

agent_reach_app = typer.Typer(
    name="agent-reach",
    help="Optional Agent Reach bridge commands.",
    no_args_is_help=True,
)
reach_app.add_typer(agent_reach_app, name="agent-reach")


# ── Native commands ──────────────────────────────────────────────────


@reach_app.command("doctor")
def doctor_command() -> None:
    """Run diagnostic checks for all Reach dependencies."""
    lines, problems = reach_doctor.run_doctor()
    for line in lines:
        typer.echo(line)
    raise typer.Exit(code=1 if problems else 0)


@reach_app.command("providers")
def providers_command() -> None:
    """List available Reach data-source providers."""
    typer.echo(reach_providers.list_providers())


@reach_app.command("install")
def install_command(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be installed without doing anything."
    ),
    safe: bool = typer.Option(
        False, "--safe", help="Show safe-mode install instructions."
    ),
) -> None:
    """Show native DevPilot Reach optional dependencies.

    Phase 1 never auto-installs system packages.
    """
    deps = [
        ("gh",         "GitHub CLI",    "https://cli.github.com/"),
        ("yt-dlp",     "yt-dlp",        "pip install yt-dlp"),
        ("feedparser", "feedparser",    "pip install feedparser"),
    ]
    if dry_run:
        typer.echo("Optional dependencies for DevPilot Reach:\n")
        for name, label, install in deps:
            import shutil
            found = shutil.which(name) if name != "feedparser" else _can_import(name)
            status = "installed" if found else "MISSING"
            typer.echo(f"  {label:15s}  {status:10s}  {install}")
        typer.echo("\nNo changes were made (--dry-run).")
    elif safe:
        typer.echo("Safe-mode install instructions:\n")
        for name, label, install in deps:
            typer.echo(f"  {label}: {install}")
        typer.echo(
            "\nInstall each dependency manually.  DevPilot Reach will "
            "never auto-install system packages in Phase 1."
        )
    else:
        typer.echo(
            "Use --dry-run to preview optional dependencies,\n"
            "or --safe to see safe-mode install instructions.\n\n"
            "DevPilot Reach never auto-installs system packages in Phase 1."
        )


@reach_app.command("visit")
def visit_command(
    url: str = typer.Argument(..., help="The URL to visit."),
    max_chars: int = typer.Option(
        8000, "--max-chars", help="Maximum characters to return."
    ),
) -> None:
    """Fetch a URL via Jina Reader and return readable text."""
    try:
        result = web_channel.visit(url, max_chars=max_chars)
    except Exception as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    typer.echo(result)


@reach_app.command("search")
def search_command(
    query: str = typer.Argument(..., help="The search query."),
) -> None:
    """Run a web search using the configured DevPilot search endpoint."""
    result = search_channel.search(query)
    typer.echo(result)


@reach_app.command("github")
def github_command(
    subcommand: str = typer.Argument(..., help="Subcommand (currently only 'repo')."),
    owner_repo: str = typer.Argument(..., help="Repository in owner/repo format."),
) -> None:
    """Fetch GitHub repository information via the gh CLI."""
    if subcommand != "repo":
        typer.secho(
            f"Unknown github subcommand: {subcommand!r}. Use 'repo'.",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=2)
    result = github_channel.repo_view(owner_repo)
    typer.echo(result)


@reach_app.command("youtube")
def youtube_command(
    url: str = typer.Argument(..., help="YouTube video URL."),
) -> None:
    """Fetch YouTube video metadata and subtitles (no media download)."""
    result = youtube_channel.fetch(url)
    typer.echo(result)


@reach_app.command("rss")
def rss_command(
    url: str = typer.Argument(..., help="RSS/Atom feed URL."),
    max_entries: int = typer.Option(
        15, "--max-entries", help="Maximum number of feed entries to show."
    ),
) -> None:
    """Fetch and display recent entries from an RSS/Atom feed."""
    result = rss_channel.fetch(url, max_entries=max_entries)
    typer.echo(result)


# ── Agent Reach bridge commands ──────────────────────────────────────


@agent_reach_app.command("status")
def agent_reach_status() -> None:
    """Check whether agent-reach is installed."""
    typer.echo(agent_reach_bridge.status_text())


@agent_reach_app.command("doctor")
def agent_reach_doctor() -> None:
    """Run agent-reach doctor (only if installed)."""
    result = agent_reach_bridge.run_doctor()
    typer.echo(result)


@agent_reach_app.command("install-help")
def agent_reach_install_help() -> None:
    """Print official Agent Reach install guidance."""
    typer.echo(agent_reach_bridge.install_help_text())


@agent_reach_app.command("update-help")
def agent_reach_update_help() -> None:
    """Print official Agent Reach update guidance."""
    typer.echo(agent_reach_bridge.update_help_text())


# ── Evidence sub-group ───────────────────────────────────────────────

evidence_app = typer.Typer(
    name="evidence",
    help="Browse and search collected Reach research evidence.",
    no_args_is_help=True,
)
reach_app.add_typer(evidence_app, name="evidence")


def _resolve_session_dir_for_reach(session: str | None) -> Path:
    from pathlib import Path
    from ..._app import CONFIG_DIR_NAME

    cwd = Path(".").resolve()
    if session:
        candidate = Path(session)
        if candidate.is_absolute() and candidate.exists():
            return candidate.resolve()
        if candidate.exists():
            return candidate.resolve()
        sessions_root = cwd / CONFIG_DIR_NAME / "sessions"
        by_name = sessions_root / str(session)
        if by_name.exists():
            return by_name.resolve()
        typer.secho(f"Error: Session '{session}' not found.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    else:
        # Find latest session under <cwd>/.devpilot/sessions/
        sessions_root = cwd / CONFIG_DIR_NAME / "sessions"
        if sessions_root.exists() and sessions_root.is_dir():
            subdirs = [
                d for d in sessions_root.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ]
            if subdirs:
                subdirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
                return subdirs[0].resolve()
        typer.secho(
            "Error: No session specified, and no existing sessions found in .devpilot/sessions/.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)


def _print_evidence_record(r: dict) -> None:
    timestamp = r.get("timestamp", "")
    tool = r.get("tool", "")
    source = r.get("source", "")
    query = r.get("query", "")
    title = r.get("title")
    cycle = r.get("cycle_id")
    hypothesis = r.get("hypothesis_id")
    content = r.get("content", "").strip()

    title_part = f" - {title}" if title else ""
    cycle_part = f" [cycle: {cycle}]" if cycle else ""
    hypo_part = f" [idea: {hypothesis}]" if hypothesis else ""
    query_part = f" [query: {query}]" if query else ""

    typer.echo(f"[{timestamp}] {tool}: {source}{query_part}{title_part}{cycle_part}{hypo_part}")
    if content:
        excerpt = content[:150].replace("\n", " ").strip()
        if len(content) > 150:
            excerpt += "..."
        typer.echo(f"  Excerpt: {excerpt}")
    typer.echo("")


@evidence_app.command("list")
def evidence_list(
    session: str = typer.Argument(
        None, help="Session name or directory path. Defaults to latest session."
    ),
) -> None:
    """List all evidence collected in a session."""
    from ...core.tools.reach.evidence import list_reach_evidence

    session_dir = _resolve_session_dir_for_reach(session)
    records = list_reach_evidence(str(session_dir))
    if not records:
        typer.echo(f"No evidence records found in session: {session_dir.name}")
        return

    typer.echo(f"Collected {len(records)} evidence record(s) in session: {session_dir.name}\n")
    for r in records:
        _print_evidence_record(r)


@evidence_app.command("search")
def evidence_search(
    query: str = typer.Argument(..., help="The search query."),
    session: str = typer.Argument(
        None, help="Session name or directory path. Defaults to latest session."
    ),
) -> None:
    """Search collected evidence matching a query term."""
    from ...core.tools.reach.evidence import search_reach_evidence

    session_dir = _resolve_session_dir_for_reach(session)
    records = search_reach_evidence(str(session_dir), query)
    if not records:
        typer.echo(f"No evidence matching '{query}' in session: {session_dir.name}")
        return

    typer.echo(f"Found {len(records)} matching evidence record(s) in session: {session_dir.name}\n")
    for r in records:
        _print_evidence_record(r)


@evidence_app.command("show")
def evidence_show(
    session: str = typer.Argument(
        None, help="Session name or directory path. Defaults to latest session."
    ),
    limit: int = typer.Option(
        20, "--limit", help="Maximum number of records to display."
    ),
) -> None:
    """Show collected evidence (latest first, up to limit)."""
    from ...core.tools.reach.evidence import list_reach_evidence

    session_dir = _resolve_session_dir_for_reach(session)
    records = list_reach_evidence(str(session_dir))
    if not records:
        typer.echo(f"No evidence records found in session: {session_dir.name}")
        return

    # Show latest first
    to_show = list(reversed(records))[:limit]
    typer.echo(f"Showing {len(to_show)} of {len(records)} latest evidence record(s) in session: {session_dir.name}\n")
    for r in to_show:
        _print_evidence_record(r)


# ── Helpers ──────────────────────────────────────────────────────────


def _can_import(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False

