"""Helpers for finding and summarizing iFixAi reports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ifixai_bridge import find_project_root
from .runner import audit_output_dir


@dataclass(frozen=True)
class AuditReportSummary:
    path: Path
    provider: str | None
    suite: str | None
    grade: str | None
    passed: bool | None
    total_tests: int | None
    failed_tests: list[str]
    warnings: list[str]


def find_latest_report(project_root: Path | str | None = None) -> Path | None:
    """Return the newest JSON report produced under DevPilot's audit directory."""

    root = find_project_root(project_root)
    candidates: list[Path] = []
    for base in (audit_output_dir(root), root / "ifixai-results"):
        if base.exists():
            candidates.extend(path for path in base.rglob("*.json") if path.is_file())
    if not candidates:
        return None
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0]


def load_report_summary(path: Path) -> AuditReportSummary:
    """Load a compact report summary from an iFixAi JSON report."""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AuditReportSummary(
            path=path,
            provider=None,
            suite=None,
            grade=None,
            passed=None,
            total_tests=None,
            failed_tests=[],
            warnings=[],
        )

    metadata = _as_dict(data.get("metadata"))
    overall = _as_dict(data.get("overall"))
    insights = _as_dict(data.get("insights"))
    provider = _first_text(
        metadata,
        ("provider", "model_provider", "sut_provider", "system_provider"),
    )
    suite = _first_text(metadata, ("suite", "fixture", "fixture_name"))
    grade = _first_text(overall, ("grade",)) or _first_text(insights, ("grade",)) or _text(data.get("grade"))
    passed = _first_bool(overall, ("passed",)) if overall else None
    if passed is None:
        passed = _first_bool(insights, ("passed",))
    total_tests = _first_int(insights, ("total_tests",)) or _first_int(overall, ("total_tests",))
    failed = _failed_tests(data)
    warnings = [str(item) for item in data.get("warnings", []) if item]
    return AuditReportSummary(
        path=path,
        provider=provider,
        suite=suite,
        grade=grade,
        passed=passed,
        total_tests=total_tests,
        failed_tests=failed,
        warnings=warnings[:5],
    )


def format_report_summary(summary: AuditReportSummary) -> str:
    """Render a compact human-readable summary."""

    lines = [f"Latest iFixAi report: {summary.path}"]
    if summary.provider:
        lines.append(f"Provider: {summary.provider}")
    if summary.suite:
        lines.append(f"Suite/fixture: {summary.suite}")
    if summary.grade:
        lines.append(f"Grade: {summary.grade}")
    if summary.passed is not None:
        lines.append(f"Passed: {'yes' if summary.passed else 'no'}")
    if summary.total_tests is not None:
        lines.append(f"Tests: {summary.total_tests}")
    if summary.failed_tests:
        lines.append("Failed inspections:")
        for name in summary.failed_tests[:10]:
            lines.append(f"  - {name}")
    if summary.warnings:
        lines.append("Warnings:")
        for warning in summary.warnings:
            lines.append(f"  - {warning}")
    return "\n".join(lines)


def _failed_tests(data: dict[str, Any]) -> list[str]:
    tests = data.get("test_results") or data.get("results") or data.get("tests") or []
    failed: list[str] = []
    if not isinstance(tests, list):
        return failed
    for item in tests:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").lower()
        passing = item.get("passing")
        if status == "fail" or passing is False:
            name = item.get("test_id") or item.get("id") or item.get("name") or "unknown"
            label = str(name)
            title = item.get("name")
            if title and str(title) != label:
                label = f"{label}: {title}"
            failed.append(label)
    return failed


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_text(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _text(data.get(key))
        if value:
            return value
    return None


def _first_bool(data: dict[str, Any], keys: tuple[str, ...]) -> bool | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool):
            return value
    return None


def _first_int(data: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None
