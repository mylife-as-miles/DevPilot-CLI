"""Graceful readers for DevPilot session artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_report(session_dir: str | Path) -> str:
    path = Path(session_dir) / "REPORT.md"
    return _read_text(path)


def read_reach_evidence(session_dir: str | Path) -> list[dict[str, Any]]:
    return _read_jsonl(Path(session_dir) / "reach_evidence.jsonl")


def read_idea_tree(session_dir: str | Path) -> dict[str, Any]:
    base = Path(session_dir)
    for path in (base / ".coordinator" / "idea_tree.json", base / "idea_tree.json"):
        data = _read_json(path)
        if data:
            return data
    return {}


def read_run_info(session_dir: str | Path) -> dict[str, Any]:
    return _read_json(Path(session_dir) / "run_info.json")


def read_executor_summaries(session_dir: str | Path) -> list[dict[str, Any]]:
    base = Path(session_dir)
    summaries: list[dict[str, Any]] = []

    jsonl_path = base / "executor_summaries.jsonl"
    for record in _read_jsonl(jsonl_path):
        if isinstance(record, dict):
            summaries.append(record)

    experiments = base / "experiments"
    if experiments.is_dir():
        for exp_dir in sorted(p for p in experiments.iterdir() if p.is_dir()):
            report = _read_text(exp_dir / "report.md")
            metrics = _read_json(exp_dir / "metrics.json")
            diff = _read_text(exp_dir / "diff.patch", max_chars=2000)
            if report or metrics or diff:
                summaries.append({
                    "node_id": exp_dir.name,
                    "report": report,
                    "metrics": metrics,
                    "diff": diff,
                    "path": str(exp_dir),
                })

    legacy = _read_jsonl(base / "experiments.jsonl")
    for record in legacy:
        if isinstance(record, dict):
            summaries.append(record)

    return summaries


def _read_text(path: Path, *, max_chars: int = 20000) -> str:
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) > max_chars:
        return text[:max_chars]
    return text


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict):
                    records.append(data)
    except OSError:
        return []
    return records
