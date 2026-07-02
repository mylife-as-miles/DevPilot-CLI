"""Agent Reach bridge — detect, run, and print guidance for the external tool.

This module never auto-installs Agent Reach or modifies OpenClaw config.
It only detects presence, proxies ``agent-reach doctor``, and prints
human-readable install/update instructions.
"""

from __future__ import annotations

from .subprocess_utils import is_available, run_safe


_AGENT_REACH_BIN = "agent-reach"

_INSTALL_URL = (
    "https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/install.md"
)
_UPDATE_URL = (
    "https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/update.md"
)


# ── Detection ────────────────────────────────────────────────────────


def is_installed() -> bool:
    """Return True if ``agent-reach`` is on PATH."""
    return is_available(_AGENT_REACH_BIN)


def status_text() -> str:
    """Human-readable one-liner for ``agent-reach status``."""
    if is_installed():
        return f"agent-reach: installed (found on PATH)"
    return "agent-reach: not installed"


# ── Doctor proxy ─────────────────────────────────────────────────────


def run_doctor(timeout: int = 30) -> str:
    """Run ``agent-reach doctor`` and return its output.

    Returns a guidance string if agent-reach is not installed.
    """
    if not is_installed():
        return (
            "agent-reach is not installed.\n\n"
            "Run `devpilot reach agent-reach install-help` for installation guidance."
        )
    try:
        result = run_safe([_AGENT_REACH_BIN, "doctor"], timeout=timeout)
        output = (result.stdout or "") + (result.stderr or "")
        return output.strip() or "(agent-reach doctor returned no output)"
    except FileNotFoundError:
        return "agent-reach binary not found despite being on PATH."
    except Exception as exc:
        return f"Failed to run agent-reach doctor: {type(exc).__name__}: {exc}"


# ── Instruction text ─────────────────────────────────────────────────


def install_help_text() -> str:
    """Return the official Agent Reach install guidance text."""
    lines = [
        "Ask your coding agent:",
        "",
        f"帮我安装 Agent Reach：{_INSTALL_URL}",
        "",
        "Safe mode:",
        "",
        f"帮我安装 Agent Reach（安全模式）：{_INSTALL_URL}",
        "安装时使用 --safe 参数",
        "",
        "─── OpenClaw users ───",
        "",
        "OpenClaw needs exec/coding permission because Agent Reach",
        "depends on shell commands.  Before asking OpenClaw to install,",
        "run these two commands in your OpenClaw terminal:",
        "",
        '  openclaw config set tools.profile "coding"',
        "  openclaw gateway restart",
        "",
        "Then ask OpenClaw to install Agent Reach using the prompt above.",
    ]
    return "\n".join(lines)


def update_help_text() -> str:
    """Return the official Agent Reach update guidance text."""
    lines = [
        "Ask your coding agent:",
        "",
        f"帮我更新 Agent Reach：{_UPDATE_URL}",
        "",
        "(Do not run the update automatically in Phase 1.)",
    ]
    return "\n".join(lines)
