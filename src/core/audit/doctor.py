"""Diagnostics for ``devpilot audit``."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

from ..._app import CONFIG_DIR_NAME
from .ifixai_bridge import build_ifixai_invocation, find_project_root, find_vendored_ifixai, run_ifixai


_REQUIRED_IFIXAI_PACKAGES = (
    "click",
    "pydantic",
    "yaml",
    "jsonschema",
    "rich",
)
_OPTIONAL_RUNTIME_PACKAGES = (
    "aiohttp",
    "questionary",
    "json_repair",
    "dateutil",
)
_IFIXAI_CORE_PACKAGES = (*_REQUIRED_IFIXAI_PACKAGES, *_OPTIONAL_RUNTIME_PACKAGES)


def missing_ifixai_core_packages() -> list[str]:
    """Return iFixAi core runtime packages missing from the active environment."""

    return [package for package in _IFIXAI_CORE_PACKAGES if importlib.util.find_spec(package) is None]


def run_doctor(project_root: Path | str | None = None) -> tuple[list[str], int]:
    """Run audit diagnostics and return ``(lines, problem_count)``."""

    root = find_project_root(project_root)
    lines: list[str] = ["DevPilot Audit doctor", ""]
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

    lines.append("project-local storage")
    audit_dir = root / CONFIG_DIR_NAME / "audit"
    try:
        audit_dir.mkdir(parents=True, exist_ok=True)
        probe = audit_dir / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        ok(f"audit workspace is writable: {audit_dir}")
    except OSError as exc:
        fail(f"audit workspace is not writable: {audit_dir}", str(exc))

    home = Path.home().resolve()
    try:
        audit_dir.resolve().relative_to(home)
        under_home = True
    except ValueError:
        under_home = False
    if under_home and not _is_relative_to(audit_dir.resolve(), root.resolve()):
        fail("audit storage resolved outside the active project")
    else:
        ok("no global audit storage is used")

    lines.append("")
    lines.append("iFixAi upstream")
    vendored = find_vendored_ifixai(root)
    if vendored is None:
        invocation = build_ifixai_invocation(["--help"], cwd=root)
        if invocation is None:
            fail("iFixAi is not vendored and no CLI fallback was found", "Expected vendor/iFixAi or an ifixai executable.")
        else:
            ok(f"iFixAi resolved from {invocation.source}")
    else:
        ok(f"vendored iFixAi found: {vendored}")
        pyproject = vendored / "pyproject.toml"
        license_file = vendored / "LICENSE"
        text = pyproject.read_text(encoding="utf-8", errors="replace") if pyproject.exists() else ""
        if "Apache-2.0" in text and license_file.exists():
            ok("upstream Apache-2.0 license is present")
        else:
            fail("upstream license metadata is missing", "Keep vendor/iFixAi unmodified with its LICENSE file.")

    lines.append("")
    lines.append("python runtime")
    if sys.version_info >= (3, 10):
        ok(f"Python {sys.version_info.major}.{sys.version_info.minor} is supported")
    else:
        fail("Python 3.10 or newer is required")

    for package in _REQUIRED_IFIXAI_PACKAGES:
        if importlib.util.find_spec(package):
            ok(f"{package} importable")
        else:
            warn(f"{package} is not installed", "Run `devpilot audit install --dry-run` for setup guidance.")
    for package in _OPTIONAL_RUNTIME_PACKAGES:
        if importlib.util.find_spec(package):
            ok(f"{package} importable")
        else:
            warn(f"{package} is not installed", "Some iFixAi commands may need this dependency.")

    lines.append("")
    lines.append("DevPilot audit modules")
    for module in (
        "devpilot.core.audit.ifixai_bridge",
        "devpilot.core.audit.doctor",
        "devpilot.core.audit.runner",
        "devpilot.core.audit.reports",
        "devpilot.core.audit.devpilot_adapter",
        "devpilot.cli.commands.audit_cmd",
    ):
        try:
            importlib.import_module(module)
            ok(f"{module} importable")
        except Exception as exc:
            fail(f"{module} import failed", str(exc))

    help_result = run_ifixai(["--help"], cwd=root, timeout=30)
    if help_result.ok:
        ok(f"iFixAi CLI help runs via {help_result.source}")
    else:
        warn("iFixAi CLI did not run cleanly", _compact(help_result.stderr or help_result.stdout or help_result.error or "unknown error"))

    lines.append("")
    if problems:
        lines.append(f"{problems} issue(s) found.")
    else:
        lines.append("all required audit checks passed.")
    return lines, problems


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _compact(text: str, limit: int = 240) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."
