"""`devpilot login` — subscription OAuth login (experimental).

Currently supports ChatGPT (OpenAI) subscriptions: ``devpilot login openai`` runs a
browser OAuth flow so Plus/Pro/Team subscribers can drive DevPilot with their
subscription instead of a pay-per-token API key.

Heads-up: using a ChatGPT subscription token with third-party tooling may
violate OpenAI's terms and can get the account rate-limited or banned. This is
strictly opt-in.
"""

from __future__ import annotations

import typer

from ..._app import GLOBAL_CONFIG_FILE
from .config_cmd import write_user_llm_config

login_app = typer.Typer(
    name="login",
    help="Sign in with a model subscription (experimental).",
    no_args_is_help=True,
)


@login_app.command("openai")
def login_openai(
    no_browser: bool = typer.Option(
        False, "--no-browser",
        help="Print the auth URL instead of opening a browser.",
    ),
    set_default: bool = typer.Option(
        True, "--set-default/--no-set-default",
        help="Write provider=openai-oauth to the global config after login.",
    ),
) -> None:
    """Log in to ChatGPT and store the subscription token under ~/.devpilot/oauth/."""
    from ...core.oauth import openai as oauth
    from ..style import console as _console

    _console.print(
        "[yellow]Experimental:[/] using a ChatGPT subscription token with "
        "third-party tools may violate OpenAI's terms and risks your account."
    )
    try:
        tokens = oauth.login(open_browser=not no_browser)
    except oauth.OAuthError as exc:
        _console.print(f"[red]login failed:[/] {exc}")
        raise typer.Exit(code=1)

    plan = tokens.plan_type or "unknown"
    who = tokens.account_id or "(account id unavailable)"
    _console.print(f"[green]✓[/] signed in to ChatGPT — plan=[bold]{plan}[/], account={who}")

    if set_default:
        from .._constants import DEFAULT_OPENAI_OAUTH_MODEL

        model = DEFAULT_OPENAI_OAUTH_MODEL
        write_user_llm_config({"provider": "openai-oauth", "model": model})
        _console.print(
            f"[green]✓[/] set provider=openai-oauth (model={model}) in {GLOBAL_CONFIG_FILE}"
        )
    _console.print("Run [bold]devpilot[/] to start a session.")


@login_app.command("status")
def login_status() -> None:
    """Show the current ChatGPT login state."""
    from ...core.oauth import openai as oauth
    from ..style import console as _console

    tokens = oauth.load_tokens()
    if tokens is None:
        _console.print("[yellow]not signed in[/] — run `devpilot login openai`")
        raise typer.Exit(code=1)
    plan = tokens.plan_type or "unknown"
    state = "expired (will refresh)" if tokens.is_expired else "valid"
    _console.print(
        f"[green]signed in[/] to ChatGPT — plan=[bold]{plan}[/], "
        f"account={tokens.account_id or 'unknown'}, access token {state}"
    )


@login_app.command("logout")
def login_logout() -> None:
    """Delete the stored ChatGPT subscription token."""
    from ...core.oauth import openai as oauth
    from ..style import console as _console

    if oauth.clear_tokens():
        _console.print("[green]✓[/] removed stored ChatGPT token")
    else:
        _console.print("[dim]nothing to remove (not signed in)[/]")
