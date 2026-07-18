"""Safe subprocess bridge to the optional Headroom CLI."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Mapping, Sequence

from .types import HeadroomInvocation, RunResult


VENDORED_HEADROOM = Path("vendor") / "headroom"
DEFAULT_TIMEOUT_SECONDS = 300
_SECRET_FLAGS = {"--api-key", "--anthropic-api-key", "--openai-api-key", "--token"}


def find_project_root(start: Path | str | None = None) -> Path:
    current = Path(start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
            return candidate
    return current


def find_vendored_headroom(repo_root: Path) -> Path | None:
    candidate = Path(repo_root).resolve() / VENDORED_HEADROOM
    if (candidate / "pyproject.toml").is_file() and (candidate / "headroom").is_dir():
        return candidate
    return None


def build_headroom_invocation(
    args: Sequence[str],
    *,
    cwd: Path | str | None = None,
) -> HeadroomInvocation | None:
    root = find_project_root(cwd)
    vendored = find_vendored_headroom(root)
    if vendored is not None:
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            str(vendored)
            if not existing_pythonpath
            else str(vendored) + os.pathsep + existing_pythonpath
        )
        env.setdefault("HEADROOM_DISABLE_UPDATE_CHECK", "1")
        return HeadroomInvocation(
            argv=[sys.executable, "-m", "headroom.cli", *list(args)],
            cwd=root,
            env=env,
            source="vendored",
        )

    if shutil.which("headroom"):
        return HeadroomInvocation(argv=["headroom", *list(args)], cwd=root, env=None, source="path")

    if shutil.which("uvx"):
        return HeadroomInvocation(
            argv=["uvx", "--from", "headroom-ai", "headroom", *list(args)],
            cwd=root,
            env=None,
            source="uvx",
        )

    return None


def build_headroom_command(args: list[str]) -> list[str]:
    invocation = build_headroom_invocation(args)
    if invocation is None:
        return ["headroom", *args]
    return list(invocation.argv)


def is_headroom_available(project_root: Path | str | None = None) -> bool:
    return build_headroom_invocation(["--help"], cwd=project_root) is not None


def run_headroom(
    args: list[str],
    cwd: Path | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    extra_env: Mapping[str, str] | None = None,
) -> RunResult:
    root = find_project_root(cwd)
    invocation = build_headroom_invocation(args, cwd=root)
    if invocation is None:
        return RunResult(
            argv=redact_args(["headroom", *args]),
            returncode=127,
            stdout="",
            stderr="Headroom is not available. Run `devpilot compress install --dry-run` for setup guidance.",
            cwd=str(root),
            source="missing",
            error="missing",
        )
    return _run_invocation(invocation, timeout=timeout, extra_env=extra_env)


def run_headroom_python(
    script: str,
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    extra_env: Mapping[str, str] | None = None,
) -> RunResult:
    root = find_project_root(cwd)
    invocation = build_headroom_invocation([], cwd=root)
    if invocation is None:
        return RunResult(
            argv=redact_args(["headroom-python", *args]),
            returncode=127,
            stdout="",
            stderr="Headroom is not available. Run `devpilot compress install --dry-run` for setup guidance.",
            cwd=str(root),
            source="missing",
            error="missing",
        )
    py = invocation.argv[0]
    if len(invocation.argv) >= 3 and invocation.argv[1] == "-m":
        argv = [py, "-c", script, *args]
    elif invocation.source == "uvx":
        argv = ["uvx", "--from", "headroom-ai", "python", "-c", script, *args]
    else:
        argv = [sys.executable, "-c", script, *args]
    py_invocation = HeadroomInvocation(argv=argv, cwd=invocation.cwd, env=invocation.env, source=invocation.source)
    return _run_invocation(py_invocation, timeout=timeout, extra_env=extra_env)


def _run_invocation(
    invocation: HeadroomInvocation,
    *,
    timeout: int,
    extra_env: Mapping[str, str] | None = None,
) -> RunResult:
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
            stderr=f"{exc}\nRun `devpilot compress install --dry-run` for setup guidance.",
            cwd=str(invocation.cwd),
            source=invocation.source,
            error="missing",
        )
    except subprocess.TimeoutExpired as exc:
        return RunResult(
            argv=redact_args(invocation.argv),
            returncode=124,
            stdout=_coerce_text(exc.stdout),
            stderr=_coerce_text(exc.stderr) or f"Headroom timed out after {timeout}s.",
            cwd=str(invocation.cwd),
            source=invocation.source,
            error="timeout",
            timed_out=True,
        )

    return RunResult(
        argv=redact_args(invocation.argv),
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        cwd=str(invocation.cwd),
        source=invocation.source,
    )


def redact_args(args: Sequence[str]) -> list[str]:
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


def _coerce_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)
