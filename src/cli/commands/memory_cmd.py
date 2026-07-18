"""`devpilot memory` - optional MemPalace long-term recall commands."""

from __future__ import annotations

from pathlib import Path

import typer

from ...core.memory_palace import doctor as memory_doctor
from ...core.memory_palace.install import install_guidance
from ...core.memory_palace.runner import (
    ensure_memory_workspace,
    initialize_project,
    mine_exports,
    mine_path,
    search_memory,
    status,
    wake_up,
)
from ...core.memory_palace.sync import sync_evidence_exports, sync_sessions_export
from ...core.memory_palace.types import RunResult


memory_app = typer.Typer(
    name="memory",
    help="Optional MemPalace-backed long-term semantic memory.",
    no_args_is_help=True,
)


@memory_app.command("doctor")
def doctor_command() -> None:
    """Check the local MemPalace integration."""

    lines, problems = memory_doctor.run_doctor(Path(".").resolve())
    for line in lines:
        typer.echo(line)
    raise typer.Exit(code=1 if problems else 0)


@memory_app.command("install")
def install_command(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show setup steps without changing anything."),
    safe: bool = typer.Option(False, "--safe", help="Show safe manual installation guidance."),
) -> None:
    """Show safe setup guidance for MemPalace."""

    if not dry_run and not safe:
        typer.echo("Use --dry-run to preview setup guidance, or --safe for manual install notes.")
        typer.echo("DevPilot does not auto-install MemPalace dependencies from this command.")
        return
    typer.echo(install_guidance().rstrip())


@memory_app.command("init")
def init_command(
    timeout: int = typer.Option(300, "--timeout", min=1, help="Wall-clock timeout in seconds."),
) -> None:
    """Initialize a project-local MemPalace workspace."""

    root = Path(".").resolve()
    ensure_memory_workspace(root)
    result = initialize_project(root, timeout=timeout)
    typer.echo("Initialized DevPilot memory workspace under .devpilot/memory.")
    _print_result(result)
    _exit_if_needed(result)


@memory_app.command("mine")
def mine_command(
    path: str = typer.Option(None, "--path", help="Project path to mine. Defaults to current directory."),
    sessions: bool = typer.Option(False, "--sessions", help="Mine .devpilot/sessions."),
    evidence: bool = typer.Option(False, "--evidence", help="Export and mine DevPilot evidence artifacts."),
    all_: bool = typer.Option(False, "--all", help="Mine project, sessions, and evidence exports."),
    timeout: int = typer.Option(300, "--timeout", min=1, help="Wall-clock timeout in seconds."),
) -> None:
    """Mine project files or DevPilot artifacts into MemPalace."""

    root = Path(".").resolve()
    ensure_memory_workspace(root)
    results: list[RunResult] = []

    mine_project = all_ or (not sessions and not evidence)
    mine_sessions = all_ or sessions
    mine_evidence = all_ or evidence

    if mine_project:
        results.append(mine_path(path or ".", project_root=root, timeout=timeout))
    if mine_sessions:
        export = sync_sessions_export(root)
        typer.echo(export.message)
        if export.files:
            results.append(mine_path(root / ".devpilot" / "sessions", project_root=root, timeout=timeout))
    if mine_evidence:
        export = sync_evidence_exports(root)
        typer.echo(export.message)
        if export.files:
            results.append(mine_exports(root, timeout=timeout))

    if not results:
        typer.echo("No mineable DevPilot artifacts found.")
        return

    code = 0
    for result in results:
        _print_result(result)
        if _should_exit_nonzero(result):
            code = result.returncode
    if code:
        raise typer.Exit(code=code)


@memory_app.command("sync-evidence")
def sync_evidence_command(
    timeout: int = typer.Option(300, "--timeout", min=1, help="Wall-clock timeout in seconds."),
) -> None:
    """Export Reach evidence and learning artifacts, then mine the export."""

    root = Path(".").resolve()
    export = sync_evidence_exports(root)
    typer.echo(export.message)
    if not export.files:
        return
    result = mine_exports(root, timeout=timeout)
    _print_result(result)
    _exit_if_needed(result)


@memory_app.command("sync-sessions")
def sync_sessions_command(
    timeout: int = typer.Option(300, "--timeout", min=1, help="Wall-clock timeout in seconds."),
) -> None:
    """Export compact session summaries, then mine them."""

    root = Path(".").resolve()
    export = sync_sessions_export(root)
    typer.echo(export.message)
    if not export.files:
        return
    result = mine_path(root / ".devpilot" / "sessions", project_root=root, timeout=timeout)
    _print_result(result)
    _exit_if_needed(result)


@memory_app.command("search")
def search_command(
    query: str = typer.Argument(..., help="Memory query."),
    limit: int = typer.Option(10, "--limit", min=1, help="Maximum result count."),
    wing: str = typer.Option(None, "--wing", help="Limit search to a MemPalace wing/project."),
    raw: bool = typer.Option(False, "--raw", help="Print raw MemPalace output."),
    timeout: int = typer.Option(120, "--timeout", min=1, help="Wall-clock timeout in seconds."),
) -> None:
    """Search MemPalace memory."""

    result = search_memory(query, project_root=Path(".").resolve(), limit=limit, wing=wing, timeout=timeout)
    if raw:
        _print_result(result)
    else:
        _print_result(result, compact=True)
    _exit_if_needed(result)


@memory_app.command("wake-up")
def wake_up_command(
    query: str = typer.Option(None, "--query", help="Optional goal or context to bias recall."),
    max_chars: int = typer.Option(6000, "--max-chars", min=200, help="Maximum characters to print."),
    timeout: int = typer.Option(120, "--timeout", min=1, help="Wall-clock timeout in seconds."),
) -> None:
    """Print compact MemPalace wake-up context."""

    result = wake_up(project_root=Path(".").resolve(), query=query, max_chars=max_chars, timeout=timeout)
    _print_result(result)
    _exit_if_needed(result)


@memory_app.command("status")
def status_command(
    timeout: int = typer.Option(120, "--timeout", min=1, help="Wall-clock timeout in seconds."),
) -> None:
    """Show MemPalace status for this project."""

    result = status(Path(".").resolve(), timeout=timeout)
    _print_result(result)
    _exit_if_needed(result)


@memory_app.command("mcp-help")
def mcp_help_command() -> None:
    """Print MemPalace MCP setup guidance without editing user config."""

    typer.echo(
        """\
MemPalace MCP is optional. DevPilot does not edit Claude, Cursor, or Codex
configuration automatically in Phase 1.

If MemPalace is installed, the MCP server command is:
  mempalace-mcp

Typical manual MCP command:
  mempalace mcp

Docker or remote-vector backends are optional MemPalace choices. Review their
storage behavior before enabling them because they may store verbatim text
outside this machine.
""".rstrip()
    )


def _print_result(result: RunResult, *, compact: bool = False) -> None:
    if result.stdout:
        text = result.stdout.rstrip()
        typer.echo(_compact_lines(text, 80) if compact else text)
    if result.stderr:
        typer.echo(_friendly_stderr(result.stderr), err=True)


def _exit_if_needed(result: RunResult) -> None:
    if _should_exit_nonzero(result):
        raise typer.Exit(code=result.returncode)


def _should_exit_nonzero(result: RunResult) -> bool:
    if result.returncode in (0, 127):
        return False
    stderr = result.stderr or ""
    return "ModuleNotFoundError" not in stderr and "No module named" not in stderr


def _friendly_stderr(stderr: str) -> str:
    if "ModuleNotFoundError" in stderr:
        last_line = next(
            (line for line in reversed(stderr.splitlines()) if "ModuleNotFoundError" in line),
            "A required MemPalace dependency is missing.",
        )
        return f"{last_line}\nRun `devpilot memory install --dry-run` for setup guidance."
    if "No module named" in stderr:
        return stderr.rstrip() + "\nRun `devpilot memory install --dry-run` for setup guidance."
    return stderr.rstrip()


def _compact_lines(text: str, max_lines: int) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines] + ["[truncated]"])
