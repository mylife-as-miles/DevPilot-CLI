"""`devpilot acp` — stdio Agent Client Protocol server."""

from __future__ import annotations

import asyncio

import typer


def acp_command(
    stdio: bool = typer.Option(
        False,
        "--stdio",
        help="Serve Agent Client Protocol JSON-RPC over standard input/output.",
    ),
) -> None:
    """Start the DevPilot ACP adapter.

    Protocol frames are written only to stdout. Runtime logs and child-process
    diagnostics are forwarded to stderr.
    """
    if not stdio:
        typer.secho("error: milestone one supports only `devpilot acp --stdio`", err=True)
        raise typer.Exit(code=2)

    from ...acp import run_stdio_agent

    try:
        asyncio.run(run_stdio_agent())
    except KeyboardInterrupt:
        raise typer.Exit(code=130) from None
