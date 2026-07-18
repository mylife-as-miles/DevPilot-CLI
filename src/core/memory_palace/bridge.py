"""Safe subprocess bridge to the vendored MemPalace CLI.

MemPalace is kept as upstream source under ``vendor/mempalace``. DevPilot does
not import its internals or merge its dependency tree; it invokes the public CLI
with ``shell=False`` and a timeout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

from .types import MemPalaceInvocation, RunResult


VENDORED_MEMPALACE = Path("vendor") / "mempalace"
DEFAULT_TIMEOUT_SECONDS = 300
_SECRET_FLAGS = {
    "--api-key",
    "--llm-api-key",
    "--openai-api-key",
    "--anthropic-api-key",
}


def find_project_root(start: Path | str | None = None) -> Path:
    """Find the nearest project root from *start* without using global paths."""

    current = Path(start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
            return candidate
    return current


def find_vendored_mempalace(repo_root: Path) -> Path | None:
    """Return ``vendor/mempalace`` when the exact upstream clone is present."""

    candidate = Path(repo_root).resolve() / VENDORED_MEMPALACE
    if (candidate / "pyproject.toml").is_file() and (candidate / "mempalace").is_dir():
        return candidate
    return None


def build_mempalace_invocation(
    args: Sequence[str],
    *,
    cwd: Path | str | None = None,
) -> MemPalaceInvocation | None:
    """Resolve the best local way to invoke MemPalace.

    Detection order is intentionally project-local first:
    1. ``vendor/mempalace``
    2. installed ``mempalace`` executable
    3. ``uvx mempalace``
    """

    root = find_project_root(cwd)
    vendored = find_vendored_mempalace(root)
    if vendored is not None:
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            str(vendored)
            if not existing_pythonpath
            else str(vendored) + os.pathsep + existing_pythonpath
        )
        return MemPalaceInvocation(
            argv=[sys.executable, "-m", "mempalace.cli", *list(args)],
            cwd=root,
            env=env,
            source="vendored",
        )

    if shutil.which("mempalace"):
        return MemPalaceInvocation(
            argv=["mempalace", *list(args)],
            cwd=root,
            env=None,
            source="path",
        )

    if shutil.which("uvx"):
        return MemPalaceInvocation(
            argv=["uvx", "mempalace", *list(args)],
            cwd=root,
            env=None,
            source="uvx",
        )

    return None


def is_mempalace_available(project_root: Path | str | None = None) -> bool:
    """Return True when DevPilot can build a MemPalace command."""

    return build_mempalace_invocation(["--help"], cwd=project_root) is not None


def build_mempalace_command(args: list[str]) -> list[str]:
    """Return the resolved command vector for display or tests."""

    invocation = build_mempalace_invocation(args)
    if invocation is None:
        return ["mempalace", *args]
    return list(invocation.argv)


def run_mempalace(
    args: list[str],
    cwd: Path | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    extra_env: Mapping[str, str] | None = None,
) -> RunResult:
    """Run MemPalace safely and return a structured result."""

    root = find_project_root(cwd)
    invocation = build_mempalace_invocation(args, cwd=root)
    if invocation is None:
        return RunResult(
            argv=redact_args(["mempalace", *args]),
            returncode=127,
            stdout="",
            stderr="MemPalace is not available. Run `devpilot memory install --dry-run` for setup guidance.",
            cwd=str(root),
            source="missing",
            error="missing",
        )

    env = invocation.env.copy() if invocation.env is not None else None
    if extra_env:
        env = os.environ.copy() if env is None else env
        env.update(extra_env)

    try:
        completed = subprocess.run(
            invocation.argv,
            cwd=str(invocation.cwd),
            env=env,
            shell=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return RunResult(
            argv=redact_args(invocation.argv),
            returncode=127,
            stdout="",
            stderr=f"{exc}\nRun `devpilot memory install --dry-run` for setup guidance.",
            cwd=str(invocation.cwd),
            source=invocation.source,
            error="missing",
        )
    except subprocess.TimeoutExpired as exc:
        return RunResult(
            argv=redact_args(invocation.argv),
            returncode=124,
            stdout=_coerce_text(exc.stdout),
            stderr=_coerce_text(exc.stderr) or f"MemPalace timed out after {timeout}s.",
            cwd=str(invocation.cwd),
            source=invocation.source,
            error="timeout",
            timed_out=True,
        )

    return RunResult(
        argv=redact_args(invocation.argv),
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=redact_text(completed.stderr or "", []),
        cwd=str(invocation.cwd),
        source=invocation.source,
    )


def redact_args(args: Sequence[str]) -> list[str]:
    """Redact API-key style values from a command vector before display."""

    redacted: list[str] = []
    hide_next = False
    for arg in args:
        if hide_next:
            redacted.append("<redacted>")
            hide_next = False
            continue
        if arg in _SECRET_FLAGS:
            redacted.append(arg)
            hide_next = True
            continue
        if any(arg.startswith(flag + "=") for flag in _SECRET_FLAGS):
            flag = arg.split("=", 1)[0]
            redacted.append(flag + "=<redacted>")
            continue
        redacted.append(arg)
    return redacted


def redact_text(text: str, secrets: Sequence[str]) -> str:
    """Remove known secret values from captured output."""

    clean = text or ""
    for secret in secrets:
        if secret:
            clean = clean.replace(secret, "<redacted>")
    return clean


def _coerce_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
