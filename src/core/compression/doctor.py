"""Diagnostics for ``devpilot compress``."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from ..._app import CONFIG_DIR_NAME
from .bridge import build_headroom_invocation, find_project_root, find_vendored_headroom, run_headroom
from .runner import ensure_compression_workspace


def run_doctor(project_root: str | Path | None = None) -> tuple[list[str], int]:
    root = find_project_root(project_root)
    lines = ["DevPilot Compression doctor", ""]
    problems = 0

    def ok(message: str) -> None:
        lines.append(f"  OK {message}")

    def warn(message: str, hint: str = "") -> None:
        lines.append(f"  WARN {message}")
        if hint:
            lines.append(f"       {hint}")

    def fail(message: str, hint: str = "") -> None:
        nonlocal problems
        problems += 1
        lines.append(f"  FAIL {message}")
        if hint:
            lines.append(f"       {hint}")

    lines.append("upstream")
    vendored = find_vendored_headroom(root)
    if vendored is None:
        warn("vendor/headroom was not found", "Run `git submodule update --init --recursive`.")
    else:
        ok(f"vendor/headroom found: {vendored}")
        pyproject = vendored / "pyproject.toml"
        license_file = vendored / "LICENSE"
        text = pyproject.read_text(encoding="utf-8", errors="replace") if pyproject.exists() else ""
        if pyproject.exists():
            ok("vendor/headroom/pyproject.toml found")
        else:
            fail("vendor/headroom/pyproject.toml missing")
        if "license = \"Apache-2.0\"" in text and license_file.exists():
            ok("Apache-2.0 license metadata is present")
        else:
            fail("upstream Apache-2.0 license metadata is missing")

    if sys.version_info >= (3, 10):
        ok(f"Python {sys.version_info.major}.{sys.version_info.minor} is compatible")
    else:
        fail("Python 3.10 or newer is required")

    lines.append("")
    lines.append("runtime")
    invocation = build_headroom_invocation(["--help"], cwd=root)
    if invocation is None:
        warn("Headroom CLI is not available", "Run `devpilot compress install --dry-run` for setup guidance.")
    else:
        ok(f"Headroom command resolves via {invocation.source}")
        help_result = run_headroom(["--help"], cwd=root, timeout=30)
        if help_result.ok:
            ok("Headroom CLI help runs")
        else:
            warn("Headroom CLI did not run cleanly", _compact(help_result.stderr or help_result.stdout or "unknown error"))
    warn("proxy not running", "not required for file/session compression")

    lines.append("")
    lines.append("workspace")
    try:
        out = ensure_compression_workspace(root)
        probe = out / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        ok(f"{CONFIG_DIR_NAME}/compression writable: {out}")
        out.resolve().relative_to(root.resolve())
        ok("no global storage required")
    except OSError as exc:
        fail(f"{CONFIG_DIR_NAME}/compression is not writable", str(exc))
    except ValueError:
        fail("compression workspace resolved outside the active project")

    lines.append("")
    lines.append("DevPilot compression modules")
    for module in (
        "devpilot.core.compression.bridge",
        "devpilot.core.compression.runner",
        "devpilot.core.compression.session_compressor",
        "devpilot.core.compression.evidence_compressor",
        "devpilot.core.compression.prompt_context",
        "devpilot.cli.commands.compress_cmd",
    ):
        try:
            importlib.import_module(module)
            ok(f"{module} importable")
        except Exception as exc:
            fail(f"{module} import failed", str(exc))

    lines.append("")
    lines.append(f"{problems} issue(s) found." if problems else "all required compression checks passed.")
    return lines, problems


def _compact(text: str, limit: int = 240) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."
