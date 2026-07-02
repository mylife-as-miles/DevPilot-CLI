"""``devpilot reach doctor`` — diagnostic checks for Reach dependencies."""

from __future__ import annotations

import os
import shutil
import subprocess


def run_doctor() -> tuple[list[str], int]:
    """Run all diagnostic checks and return (lines, problem_count)."""
    lines: list[str] = []
    problems = 0

    def _ok(msg: str) -> None:
        lines.append(f"  ✓ {msg}")

    def _warn(msg: str, hint: str = "") -> None:
        lines.append(f"  ! {msg}")
        if hint:
            lines.append(f"      → {hint}")

    def _fail(msg: str, hint: str = "") -> None:
        nonlocal problems
        problems += 1
        lines.append(f"  ✗ {msg}")
        if hint:
            lines.append(f"      → {hint}")

    lines.append("DevPilot Reach doctor\n")

    # ── External CLIs ────────────────────────────────────────────
    lines.append("external tools")

    if shutil.which("git"):
        try:
            v = subprocess.check_output(
                ["git", "--version"], text=True, timeout=10
            ).strip()
            _ok(v)
        except Exception:
            _warn("git found but failed to run")
    else:
        _fail("git not installed", "brew install git  /  apt install git")

    if shutil.which("gh"):
        try:
            v = subprocess.check_output(
                ["gh", "--version"], text=True, timeout=10
            ).splitlines()[0].strip()
            _ok(f"gh: {v}")
        except Exception:
            _warn("gh found but failed to run")
    else:
        _fail("gh CLI not installed", "https://cli.github.com/")

    if shutil.which("yt-dlp"):
        try:
            v = subprocess.check_output(
                ["yt-dlp", "--version"], text=True, timeout=10
            ).strip()
            _ok(f"yt-dlp: {v}")
        except Exception:
            _warn("yt-dlp found but failed to run")
    else:
        _fail("yt-dlp not installed", "pip install yt-dlp")

    # ── Python packages ──────────────────────────────────────────
    lines.append("")
    lines.append("python packages")

    try:
        import feedparser  # noqa: F401
        _ok("feedparser available")
    except ImportError:
        _fail("feedparser not installed", "pip install feedparser")

    # ── Web search config ────────────────────────────────────────
    lines.append("")
    lines.append("web search config")

    ep = os.environ.get("WEB_SEARCH_ENDPOINT")
    if ep:
        _ok(f"WEB_SEARCH_ENDPOINT = {ep}")
    else:
        _warn(
            "WEB_SEARCH_ENDPOINT not set",
            "web search unavailable — run `devpilot config init --help`",
        )

    ep_browse = os.environ.get("WEB_BROWSE_ENDPOINT")
    if ep_browse:
        _ok(f"WEB_BROWSE_ENDPOINT = {ep_browse}")
    else:
        lines.append("  · WEB_BROWSE_ENDPOINT not set (Jina Reader will be used)")

    jina_key = os.environ.get("JINA_API_KEY")
    if jina_key:
        _ok("JINA_API_KEY is set")
    else:
        lines.append("  · JINA_API_KEY not set (anonymous Jina access)")

    # ── Agent Reach ──────────────────────────────────────────────
    lines.append("")
    lines.append("agent-reach bridge")

    if shutil.which("agent-reach"):
        _ok("agent-reach is installed")
    else:
        lines.append("  · agent-reach not installed (optional)")
        lines.append("      → run `devpilot reach agent-reach install-help` for guidance")

    # ── Summary ──────────────────────────────────────────────────
    lines.append("")
    if problems == 0:
        lines.append("all checks passed.")
    else:
        lines.append(f"{problems} issue(s) — fix the items above.")

    return lines, problems
