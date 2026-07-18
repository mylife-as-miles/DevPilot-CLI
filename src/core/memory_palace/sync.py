"""Export DevPilot artifacts into markdown that MemPalace can mine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..._app import CONFIG_DIR_NAME
from .runner import append_manifest, ensure_memory_workspace, exports_dir
from .types import SyncExportResult


def sync_evidence_exports(project_root: str | Path) -> SyncExportResult:
    """Write mineable markdown exports for Reach evidence and learned memory."""

    root = Path(project_root).resolve()
    ensure_memory_workspace(root)
    out_dir = exports_dir(root)

    files: list[Path] = []
    total_records = 0

    reach_text, count = _render_reach_evidence(root)
    total_records += count
    files.extend(_write_export(out_dir / "reach_evidence.md", reach_text))

    memories_text, count = _render_memory_jsonl(root / CONFIG_DIR_NAME / "memory" / "memories.jsonl", "Learned Memories")
    total_records += count
    files.extend(_write_export(out_dir / "learned_memories.md", memories_text))

    skills_text, count = _render_memory_jsonl(root / CONFIG_DIR_NAME / "memory" / "skills.jsonl", "Skills")
    total_records += count
    files.extend(_write_export(out_dir / "skills.md", skills_text))

    trajectories_text, count = _render_memory_jsonl(root / CONFIG_DIR_NAME / "memory" / "trajectories.jsonl", "Trajectories")
    total_records += count
    files.extend(_write_export(out_dir / "trajectories.md", trajectories_text))

    reports_text, count = _render_reports(root)
    total_records += count
    files.extend(_write_export(out_dir / "reports.md", reports_text))

    append_manifest(
        root,
        {
            "action": "sync-evidence",
            "records": total_records,
            "files": [str(path) for path in files],
        },
    )
    message = "No DevPilot evidence artifacts found." if not files else f"Exported {total_records} record(s)."
    return SyncExportResult(files=files, records=total_records, message=message)


def sync_sessions_export(project_root: str | Path) -> SyncExportResult:
    """Write a compact session markdown export, if sessions exist."""

    root = Path(project_root).resolve()
    ensure_memory_workspace(root)
    sessions_root = root / CONFIG_DIR_NAME / "sessions"
    if not sessions_root.is_dir():
        append_manifest(root, {"action": "sync-sessions", "records": 0, "files": []})
        return SyncExportResult(files=[], records=0, message="No .devpilot/sessions directory found.")

    sessions = sorted(p for p in sessions_root.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not sessions:
        append_manifest(root, {"action": "sync-sessions", "records": 0, "files": []})
        return SyncExportResult(files=[], records=0, message="No sessions found.")

    lines = ["# DevPilot Sessions", ""]
    count = 0
    for session in sessions:
        lines.append(f"## Session {session.name}")
        report = _safe_read(session / "REPORT.md")
        if report:
            lines.append("")
            lines.append(_compact(report, 2000))
            count += 1
        evidence = read_jsonl(session / "reach_evidence.jsonl")
        if evidence:
            lines.append("")
            lines.append("### Reach Evidence")
            for item in evidence[:20]:
                lines.append(_bullet_record(item, session_id=session.name))
                count += 1
        if not report and not evidence:
            lines.append("")
            lines.append("No report or reach evidence found for this session.")
        lines.append("")

    out = exports_dir(root) / "sessions.md"
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    append_manifest(root, {"action": "sync-sessions", "records": count, "files": [str(out)]})
    return SyncExportResult(files=[out], records=count, message=f"Exported {len(sessions)} session(s).")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    records.append(item)
    except OSError:
        return []
    return records


def _render_reach_evidence(root: Path) -> tuple[str, int]:
    sessions_root = root / CONFIG_DIR_NAME / "sessions"
    records: list[tuple[str, dict[str, Any]]] = []
    if sessions_root.is_dir():
        for path in sorted(sessions_root.glob("*/reach_evidence.jsonl")):
            session_id = path.parent.name
            records.extend((session_id, item) for item in read_jsonl(path))
    if not records:
        return "", 0

    lines = ["# Reach Evidence", ""]
    for session_id, item in records:
        lines.append(_bullet_record(item, session_id=session_id))
    return "\n".join(lines) + "\n", len(records)


def _render_memory_jsonl(path: Path, title: str) -> tuple[str, int]:
    records = read_jsonl(path)
    if not records:
        return "", 0
    lines = [f"# {title}", ""]
    for item in records:
        lines.append(_bullet_record(item, session_id=str(item.get("session_id") or "")))
    return "\n".join(lines) + "\n", len(records)


def _render_reports(root: Path) -> tuple[str, int]:
    sessions_root = root / CONFIG_DIR_NAME / "sessions"
    if not sessions_root.is_dir():
        return "", 0
    reports = sorted(sessions_root.glob("*/REPORT.md"))
    if not reports:
        return "", 0
    lines = ["# DevPilot Reports", ""]
    for report in reports:
        lines.append(f"## Session {report.parent.name}")
        lines.append("")
        lines.append(_compact(_safe_read(report), 2500))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n", len(reports)


def _write_export(path: Path, content: str) -> list[Path]:
    if not content.strip():
        return []
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return [path]


def _bullet_record(item: dict[str, Any], *, session_id: str) -> str:
    title = item.get("title") or item.get("name") or item.get("id") or "record"
    source = item.get("source") or item.get("tool") or item.get("kind") or "unknown"
    timestamp = item.get("timestamp") or item.get("created_at") or ""
    hypothesis = item.get("hypothesis_id") or item.get("related_hypothesis_id") or ""
    tool = item.get("tool") or ""
    content = item.get("content") or item.get("description") or item.get("summary") or ""
    excerpt = _compact(str(content), 500)
    bits = [f"session={session_id}" if session_id else "", f"time={timestamp}" if timestamp else ""]
    bits.extend([
        f"source={source}" if source else "",
        f"hypothesis={hypothesis}" if hypothesis else "",
        f"tool={tool}" if tool else "",
    ])
    meta = "; ".join(bit for bit in bits if bit)
    return f"- {title} ({meta}): {excerpt}"


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _compact(text: str, limit: int) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)].rstrip() + "..."
