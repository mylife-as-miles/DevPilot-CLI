"""`devpilot audit` - local iFixAi-backed AI safety audits."""

from __future__ import annotations

from pathlib import Path

import typer

from ...core.audit import doctor as audit_doctor
from ...core.audit.ifixai_bridge import run_ifixai, run_ifixai_interactive
from ...core.audit.reports import find_latest_report, format_report_summary, load_report_summary
from ...core.audit.runner import (
    DEFAULT_SUITE,
    AuditRunConfig,
    AuditRunError,
    format_display_command,
    is_external_provider,
    run_audit,
)


audit_app = typer.Typer(
    name="audit",
    help="Run local iFixAi audits through DevPilot's safe wrapper.",
    no_args_is_help=True,
)


@audit_app.command("doctor")
def doctor_command() -> None:
    """Check the local iFixAi audit integration."""

    lines, problems = audit_doctor.run_doctor(Path(".").resolve())
    for line in lines:
        typer.echo(line)
    raise typer.Exit(code=1 if problems else 0)


@audit_app.command("install")
def install_command(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show setup steps without changing anything."),
    safe: bool = typer.Option(False, "--safe", help="Show safe manual installation guidance."),
) -> None:
    """Show safe setup guidance for the vendored iFixAi CLI."""

    if not dry_run and not safe:
        typer.echo("Use --dry-run to preview setup guidance, or --safe for manual install notes.")
        typer.echo("DevPilot does not auto-install iFixAi dependencies from this command.")
        return

    typer.echo("iFixAi is vendored under vendor/iFixAi and kept as upstream source.")
    typer.echo("No changes were made.\n")
    typer.echo("Manual setup options:")
    typer.echo("  python -m pip install -e vendor/iFixAi")
    typer.echo("  uv pip install -e vendor/iFixAi")
    typer.echo("")
    typer.echo("Provider extras, when needed:")
    typer.echo("  python -m pip install -e \"vendor/iFixAi[openai]\"")
    typer.echo("  python -m pip install -e \"vendor/iFixAi[anthropic]\"")
    typer.echo("  python -m pip install -e \"vendor/iFixAi[gemini]\"")
    typer.echo("")
    typer.echo("Zero-install upstream fallback, if uvx is available:")
    typer.echo("  uvx --from ifixai ifixai --help")


@audit_app.command("run")
def run_command(
    provider: str = typer.Option("mock", "--provider", "-p", help="iFixAi provider to run."),
    suite: str = typer.Option(DEFAULT_SUITE, "--suite", help="iFixAi suite to run."),
    model: str = typer.Option(None, "--model", help="Provider model name."),
    endpoint: str = typer.Option(None, "--endpoint", help="Provider endpoint URL."),
    eval_mode: str = typer.Option(None, "--eval-mode", help="iFixAi evaluation mode."),
    api_key_env: str = typer.Option(None, "--api-key-env", help="Environment variable containing the provider API key."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Ask iFixAi to plan the run without executing tests."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm non-mock provider runs."),
    timeout: int = typer.Option(900, "--timeout", min=1, help="Wall-clock timeout in seconds."),
) -> None:
    """Run an iFixAi audit. Defaults to the safe local mock provider."""

    provider_name = (provider or "mock").lower()
    if is_external_provider(provider_name) and not yes:
        confirmed = typer.confirm(
            f"Provider '{provider_name}' may call a paid or external service. Continue?",
            default=False,
        )
        if not confirmed:
            typer.echo("Audit cancelled before any provider call.")
            raise typer.Exit(code=1)

    config = AuditRunConfig(
        provider=provider_name,
        suite=suite or DEFAULT_SUITE,
        model=model,
        endpoint=endpoint,
        eval_mode=eval_mode,
        api_key_env=api_key_env,
        dry_run=dry_run,
        timeout=timeout,
    )
    try:
        outcome = run_audit(config, project_root=Path(".").resolve())
    except AuditRunError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    typer.echo("Running iFixAi via DevPilot audit wrapper:")
    typer.echo(f"  ifixai {format_display_command(outcome.display_args)}")
    typer.echo(f"Output directory: {outcome.output_dir}")
    if outcome.result.stdout:
        typer.echo(outcome.result.stdout.rstrip())
    if outcome.result.stderr:
        typer.echo(_friendly_stderr(outcome.result.stderr), err=True)
    raise typer.Exit(code=outcome.result.returncode)


@audit_app.command("setup")
def setup_command(
    launch: bool = typer.Option(False, "--launch", help="Launch upstream interactive iFixAi setup."),
    timeout: int = typer.Option(900, "--timeout", min=1, help="Wall-clock timeout in seconds."),
) -> None:
    """Launch upstream iFixAi setup when running in an interactive terminal."""

    typer.echo("iFixAi setup may ask for provider details. DevPilot does not store API keys.")
    if not launch:
        typer.echo("No setup was launched. Use `devpilot audit setup --launch` to run upstream interactive setup.")
        typer.echo("For non-interactive runs, provide provider keys through environment variables.")
        return
    missing = audit_doctor.missing_ifixai_core_packages()
    if missing:
        typer.echo("Setup was not launched because upstream iFixAi dependencies are missing:")
        for package in missing:
            typer.echo(f"  - {package}")
        typer.echo("Run `devpilot audit install --dry-run` for setup guidance.")
        raise typer.Exit(code=1)
    result = run_ifixai_interactive(["setup"], cwd=Path(".").resolve(), timeout=timeout)
    if result.stderr:
        typer.echo(result.stderr, err=True)
    raise typer.Exit(code=result.returncode)


@audit_app.command("report")
def report_command() -> None:
    """Show a compact summary of the latest local iFixAi report."""

    report = find_latest_report(Path(".").resolve())
    if report is None:
        typer.echo("No iFixAi reports found under .devpilot/audit/ifixai-results/.")
        return
    typer.echo(format_report_summary(load_report_summary(report)))


@audit_app.command(
    "ifixai",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    add_help_option=False,
)
def ifixai_command(ctx: typer.Context) -> None:
    """Pass arguments through to the upstream iFixAi CLI."""

    args = list(ctx.args)
    if not args:
        args = ["--help"]
    result = run_ifixai(args, cwd=Path(".").resolve(), timeout=900)
    if not result.ok and args == ["--help"]:
        typer.echo("DevPilot audit pass-through: devpilot audit ifixai [IFIXAI_ARGS]...")
        typer.echo("")
        typer.echo("Common upstream commands:")
        typer.echo("  devpilot audit ifixai setup")
        typer.echo("  devpilot audit ifixai install")
        typer.echo("  devpilot audit ifixai run --provider mock --suite smoke")
        typer.echo("")
        typer.echo("Upstream iFixAi help could not load in this environment.")
        typer.echo("Run `devpilot audit install --dry-run` if dependencies are missing.")
        raise typer.Exit(code=0)
    if result.stdout:
        typer.echo(result.stdout.rstrip())
    if result.stderr:
        typer.echo(_friendly_stderr(result.stderr), err=True)
    raise typer.Exit(code=result.returncode)


def _friendly_stderr(stderr: str) -> str:
    """Keep upstream dependency failures readable in DevPilot output."""

    if "ModuleNotFoundError" in stderr:
        last_line = next(
            (line for line in reversed(stderr.splitlines()) if "ModuleNotFoundError" in line),
            "A required iFixAi dependency is missing.",
        )
        return f"{last_line}\nRun `devpilot audit install --dry-run` for setup guidance."
    return stderr.rstrip()
