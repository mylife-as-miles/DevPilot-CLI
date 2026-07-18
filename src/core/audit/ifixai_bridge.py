"""Safe subprocess bridge to the vendored iFixAi CLI.

The upstream iFixAi repository is kept intact under ``vendor/iFixAi``.  DevPilot
does not import or modify upstream internals; it executes the public CLI with
``shell=False`` and a timeout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


VENDORED_IFIXAI = Path("vendor") / "iFixAi"
DEFAULT_TIMEOUT_SECONDS = 300
_SECRET_FLAGS = {"--api-key", "-k", "--judge-api-key"}


@dataclass(frozen=True)
class IfixAiInvocation:
    """Resolved iFixAi command invocation."""

    argv: list[str]
    cwd: Path
    env: dict[str, str] | None
    source: str


@dataclass(frozen=True)
class IfixAiResult:
    """Result returned by the iFixAi bridge."""

    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    cwd: str
    source: str
    error: str | None = None
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and self.error is None and not self.timed_out


def find_project_root(start: Path | str | None = None) -> Path:
    """Find the nearest project root from *start* without using global paths."""

    current = Path(start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
            return candidate
    return current


def find_vendored_ifixai(project_root: Path | str | None = None) -> Path | None:
    """Return the vendored iFixAi repository when present."""

    root = find_project_root(project_root)
    candidate = root / VENDORED_IFIXAI
    if (candidate / "pyproject.toml").is_file() and (candidate / "ifixai").is_dir():
        return candidate
    return None


def build_ifixai_invocation(
    args: Sequence[str],
    *,
    cwd: Path | str | None = None,
) -> IfixAiInvocation | None:
    """Resolve the best local way to invoke iFixAi."""

    root = find_project_root(cwd)
    vendored = find_vendored_ifixai(root)
    if vendored is not None:
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            str(vendored)
            if not existing_pythonpath
            else str(vendored) + os.pathsep + existing_pythonpath
        )
        return IfixAiInvocation(
            argv=[sys.executable, "-m", "ifixai.cli.main", *list(args)],
            cwd=root,
            env=env,
            source="vendored",
        )

    if shutil.which("ifixai"):
        return IfixAiInvocation(
            argv=["ifixai", *list(args)],
            cwd=root,
            env=None,
            source="path",
        )

    if shutil.which("uvx"):
        return IfixAiInvocation(
            argv=["uvx", "--from", "ifixai", "ifixai", *list(args)],
            cwd=root,
            env=None,
            source="uvx",
        )

    return None


def is_ifixai_available(project_root: Path | str | None = None) -> bool:
    """Return True when DevPilot can resolve an iFixAi command."""

    return build_ifixai_invocation(["--help"], cwd=project_root) is not None


def run_ifixai(
    args: Sequence[str],
    *,
    cwd: Path | str | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    extra_env: Mapping[str, str] | None = None,
) -> IfixAiResult:
    """Run iFixAi safely and return a structured result."""

    invocation = build_ifixai_invocation(args, cwd=cwd)
    root = find_project_root(cwd)
    if invocation is None:
        return IfixAiResult(
            argv=redact_args(["ifixai", *list(args)]),
            returncode=127,
            stdout="",
            stderr="iFixAi is not available. Run `devpilot audit install --dry-run` for setup guidance.",
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
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return IfixAiResult(
            argv=redact_args(invocation.argv),
            returncode=127,
            stdout="",
            stderr=str(exc),
            cwd=str(invocation.cwd),
            source=invocation.source,
            error="missing",
        )
    except subprocess.TimeoutExpired as exc:
        return IfixAiResult(
            argv=redact_args(invocation.argv),
            returncode=124,
            stdout=_coerce_text(exc.stdout),
            stderr=_coerce_text(exc.stderr) or f"iFixAi timed out after {timeout}s.",
            cwd=str(invocation.cwd),
            source=invocation.source,
            error="timeout",
            timed_out=True,
        )

    return IfixAiResult(
        argv=redact_args(invocation.argv),
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        cwd=str(invocation.cwd),
        source=invocation.source,
    )


def run_ifixai_interactive(
    args: Sequence[str],
    *,
    cwd: Path | str | None = None,
    timeout: int = 900,
) -> IfixAiResult:
    """Run iFixAi with inherited stdio for interactive commands such as setup."""

    invocation = build_ifixai_invocation(args, cwd=cwd)
    root = find_project_root(cwd)
    if invocation is None:
        return IfixAiResult(
            argv=redact_args(["ifixai", *list(args)]),
            returncode=127,
            stdout="",
            stderr="iFixAi is not available. Run `devpilot audit install --dry-run` for setup guidance.",
            cwd=str(root),
            source="missing",
            error="missing",
        )

    try:
        completed = subprocess.run(
            invocation.argv,
            cwd=str(invocation.cwd),
            env=invocation.env,
            shell=False,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return IfixAiResult(
            argv=redact_args(invocation.argv),
            returncode=127,
            stdout="",
            stderr=str(exc),
            cwd=str(invocation.cwd),
            source=invocation.source,
            error="missing",
        )
    except subprocess.TimeoutExpired:
        return IfixAiResult(
            argv=redact_args(invocation.argv),
            returncode=124,
            stdout="",
            stderr=f"iFixAi timed out after {timeout}s.",
            cwd=str(invocation.cwd),
            source=invocation.source,
            error="timeout",
            timed_out=True,
        )

    return IfixAiResult(
        argv=redact_args(invocation.argv),
        returncode=completed.returncode,
        stdout="",
        stderr="",
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
