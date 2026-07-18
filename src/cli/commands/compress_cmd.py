"""`devpilot compress` - optional Headroom context compression commands."""

from __future__ import annotations

from pathlib import Path

import typer

from ...core.compression import doctor as compression_doctor
from ...core.compression.evidence_compressor import compress_evidence
from ...core.compression.runner import compress_text_file, ensure_compression_workspace, status_lines
from ...core.compression.session_compressor import compress_logs, compress_session
from ...core.compression.types import CompressionArtifact, RunResult


compress_app = typer.Typer(
    name="compress",
    help="Optional Headroom-backed context compression.",
    no_args_is_help=True,
)


@compress_app.command("doctor")
def doctor_command() -> None:
    """Check the local Headroom compression integration."""

    lines, problems = compression_doctor.run_doctor(Path(".").resolve())
    for line in lines:
        typer.echo(line)
    raise typer.Exit(code=1 if problems else 0)


@compress_app.command("install")
def install_command(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show setup steps without changing anything."),
    safe: bool = typer.Option(False, "--safe", help="Show safe manual installation guidance."),
) -> None:
    """Show safe setup guidance for Headroom."""

    if not dry_run and not safe:
        typer.echo("Use --dry-run to preview setup guidance, or --safe for manual install notes.")
        typer.echo("DevPilot does not auto-install Headroom dependencies from this command.")
        return
    typer.echo(_install_guidance().rstrip())


@compress_app.command("text")
def text_command(
    file: str = typer.Argument(..., help="Text file to compress."),
    output: str = typer.Option(None, "--output", "-o", help="Optional output path."),
    max_chars: int = typer.Option(6000, "--max-chars", min=200, help="Maximum compressed characters."),
    timeout: int = typer.Option(300, "--timeout", min=1, help="Wall-clock timeout in seconds."),
) -> None:
    """Compress a single text file without mutating it."""

    result = compress_text_file(file, project_root=Path(".").resolve(), max_chars=max_chars, timeout=timeout)
    if result.stdout:
        if output:
            out = Path(output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(result.stdout.rstrip() + "\n", encoding="utf-8")
            typer.echo(f"Wrote compressed text: {out}")
        else:
            typer.echo(result.stdout.rstrip())
    _print_stderr(result)
    _exit_if_needed(result)


@compress_app.command("session")
def session_command(
    session: str = typer.Argument(None, help="Session name or directory path. Defaults to latest session."),
    max_chars: int = typer.Option(8000, "--max-chars", min=500, help="Maximum compressed characters."),
) -> None:
    """Compress a DevPilot session report and related artifacts."""

    artifact = compress_session(Path(".").resolve(), session, max_chars=max_chars)
    _print_artifact(artifact)


@compress_app.command("evidence")
def evidence_command(
    session: str = typer.Argument(None, help="Session name or directory path. Defaults to latest session."),
    max_chars: int = typer.Option(6000, "--max-chars", min=500, help="Maximum compressed characters."),
) -> None:
    """Compress Reach evidence for one session."""

    artifact = compress_evidence(Path(".").resolve(), session, max_chars=max_chars)
    _print_artifact(artifact)


@compress_app.command("logs")
def logs_command(
    session: str = typer.Argument(None, help="Session name or directory path. Defaults to latest session."),
    max_chars: int = typer.Option(6000, "--max-chars", min=500, help="Maximum compressed characters."),
) -> None:
    """Compress executor, event, and test logs for one session."""

    artifact = compress_logs(Path(".").resolve(), session, max_chars=max_chars)
    _print_artifact(artifact)


@compress_app.command("status")
def status_command() -> None:
    """Show project-local compression status."""

    for line in status_lines(Path(".").resolve()):
        typer.echo(line)


@compress_app.command("proxy-help")
def proxy_help_command() -> None:
    """Print Headroom proxy guidance without starting or wrapping anything."""

    typer.echo(
        """\
Headroom proxy is optional and is not auto-started by DevPilot Phase 1.

Manual commands:
  headroom proxy --port 8787
  headroom doctor

DevPilot file/session compression does not require a running proxy.
""".rstrip()
    )


@compress_app.command("mcp-help")
def mcp_help_command() -> None:
    """Print Headroom MCP guidance without editing agent config."""

    typer.echo(
        """\
Headroom MCP is optional. DevPilot does not edit Claude, Cursor, or Codex
configuration automatically in Phase 1.

Manual commands:
  headroom mcp install
  headroom mcp status
  headroom mcp serve

Review storage and proxy behavior before enabling MCP or proxy mode.
""".rstrip()
    )


def _print_artifact(artifact: CompressionArtifact) -> None:
    typer.echo(artifact.message)
    if artifact.path is not None:
        typer.echo(f"Output: {artifact.path}")
    for warning in artifact.warnings:
        typer.echo(warning, err=True)


def _print_stderr(result: RunResult) -> None:
    if result.stderr:
        typer.echo(_friendly_stderr(result.stderr), err=True)


def _exit_if_needed(result: RunResult) -> None:
    if result.returncode not in (0, 127):
        raise typer.Exit(code=result.returncode)


def _friendly_stderr(stderr: str) -> str:
    if "ModuleNotFoundError" in stderr or "No module named" in stderr:
        return stderr.rstrip() + "\nRun `devpilot compress install --dry-run` for setup guidance."
    return stderr.rstrip()


def _install_guidance() -> str:
    return """\
Headroom is vendored under vendor/headroom and kept as upstream Apache-2.0 source.
DevPilot does not install Headroom dependencies into its core environment.

Safe setup options:
  pip install "headroom-ai[all]"
  pip install "headroom-ai[proxy]"
  pip install "headroom-ai[mcp]"
  pip install -e vendor/headroom
  uvx --from "headroom-ai[all]" headroom doctor

Optional extras can be heavy. Do not add them to DevPilot's core environment
unless you intentionally choose that path.
"""
