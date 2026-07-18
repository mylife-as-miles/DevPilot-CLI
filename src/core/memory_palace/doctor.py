"""Diagnostics for ``devpilot memory``."""

from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path

from ..._app import CONFIG_DIR_NAME
from .bridge import build_mempalace_invocation, find_project_root, find_vendored_mempalace, run_mempalace
from .runner import ensure_memory_workspace, palace_path


def run_doctor(project_root: Path | str | None = None) -> tuple[list[str], int]:
    """Run MemPalace diagnostics and return ``(lines, problem_count)``."""

    root = find_project_root(project_root)
    lines: list[str] = ["DevPilot Memory doctor", ""]
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
    vendored = find_vendored_mempalace(root)
    if vendored is None:
        warn("vendor/mempalace was not found", "Run `git submodule update --init --recursive`.")
    else:
        ok(f"vendor/mempalace found: {vendored}")
        pyproject = vendored / "pyproject.toml"
        license_file = vendored / "LICENSE"
        text = pyproject.read_text(encoding="utf-8", errors="replace") if pyproject.exists() else ""
        if pyproject.exists():
            ok("vendor/mempalace/pyproject.toml found")
        else:
            fail("vendor/mempalace/pyproject.toml missing")
        if "license = \"MIT\"" in text and license_file.exists():
            ok("MIT license metadata is present")
        else:
            fail("upstream MIT license metadata is missing", "Keep vendor/mempalace unmodified with its LICENSE file.")

    if sys.version_info >= (3, 10):
        ok(f"Python {sys.version_info.major}.{sys.version_info.minor} is compatible with DevPilot and MemPalace")
    else:
        fail("Python 3.10 or newer is required")

    lines.append("")
    lines.append("runtime")
    invocation = build_mempalace_invocation(["--help"], cwd=root)
    if invocation is None:
        warn("MemPalace CLI is not available", "Run `devpilot memory install --dry-run` for setup guidance.")
    else:
        ok(f"MemPalace command resolves via {invocation.source}")
        help_result = run_mempalace(["--help"], cwd=root, timeout=30)
        if help_result.ok:
            ok("MemPalace CLI help runs")
        else:
            warn("MemPalace CLI did not run cleanly", _compact(help_result.stderr or help_result.stdout or "unknown error"))
    warn("isolated install recommended", "uv tool install mempalace")

    lines.append("")
    lines.append("workspace")
    try:
        mem_dir = ensure_memory_workspace(root)
        probe = mem_dir / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        ok(f"{CONFIG_DIR_NAME}/memory writable: {mem_dir}")
    except OSError as exc:
        fail(f"{CONFIG_DIR_NAME}/memory is not writable", str(exc))

    local_palace = palace_path(root)
    try:
        local_palace.resolve().relative_to(root.resolve())
        ok(f"no global storage required; local palace is {local_palace}")
    except ValueError:
        fail("palace path resolved outside the active project")

    lines.append("")
    lines.append("mcp")
    if shutil.which("mempalace-mcp"):
        ok("mempalace-mcp executable found")
    else:
        warn("mempalace-mcp not configured", "Run `devpilot memory mcp-help`.")

    lines.append("")
    lines.append("DevPilot memory modules")
    for module in (
        "devpilot.core.memory_palace.bridge",
        "devpilot.core.memory_palace.runner",
        "devpilot.core.memory_palace.sync",
        "devpilot.core.memory_palace.context",
        "devpilot.cli.commands.memory_cmd",
    ):
        try:
            importlib.import_module(module)
            ok(f"{module} importable")
        except Exception as exc:
            fail(f"{module} import failed", str(exc))

    lines.append("")
    if problems:
        lines.append(f"{problems} issue(s) found.")
    else:
        lines.append("all required memory checks passed.")
    return lines, problems


def _compact(text: str, limit: int = 240) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."
