"""Compress Reach evidence while preserving citations and hypothesis IDs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..._app import CONFIG_DIR_NAME
from .runner import append_manifest, conservative_compress_text, ensure_compression_workspace, reports_dir
from .types import CompressionArtifact


def compress_evidence(
    project_root: str | Path,
    session: str | None = None,
    *,
    max_chars: int = 6000,
) -> CompressionArtifact:
    root = Path(project_root).resolve()
    session_dir = resolve_session_dir(root, session)
    if session_dir is None:
        return CompressionArtifact(path=None, message="No sessions found in .devpilot/sessions/.")
    evidence_path = session_dir / "reach_evidence.jsonl"
    records = read_jsonl(evidence_path)
    if not records:
        return CompressionArtifact(path=None, message=f"No Reach evidence found for session {session_dir.name}.")

    lines = [f"# Compressed Reach Evidence: {session_dir.name}", ""]
    for item in records:
        lines.append(_render_evidence_item(item))
    rendered = "\n".join(lines).strip() + "\n"
    compressed = conservative_compress_text(rendered, max_chars=max_chars)

    ensure_compression_workspace(root)
    out = reports_dir(root) / f"{session_dir.name}.evidence.compressed.md"
    out.write_text(compressed + "\n", encoding="utf-8")
    append_manifest(root, {"action": "evidence", "session_id": session_dir.name, "records": len(records), "output": str(out)})
    return CompressionArtifact(path=out, content=compressed, source_count=len(records), message=f"Compressed {len(records)} evidence record(s).")


def resolve_session_dir(project_root: Path, session: str | None) -> Path | None:
    sessions_root = project_root / CONFIG_DIR_NAME / "sessions"
    if session:
        candidate = Path(session)
        if candidate.is_absolute() and candidate.is_dir():
            return candidate.resolve()
        if candidate.is_dir():
            return candidate.resolve()
        by_name = sessions_root / session
        return by_name.resolve() if by_name.is_dir() else None
    if not sessions_root.is_dir():
        return None
    sessions = [p for p in sessions_root.iterdir() if p.is_dir() and not p.name.startswith(".")]
    if not sessions:
        return None
    sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return sessions[0].resolve()


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


def _render_evidence_item(item: dict[str, Any]) -> str:
    title = item.get("title") or item.get("source") or "Evidence"
    source = item.get("source") or item.get("url") or item.get("input") or ""
    hypothesis = item.get("hypothesis_id") or item.get("related_hypothesis_id") or ""
    timestamp = item.get("timestamp") or item.get("created_at") or ""
    tool = item.get("tool") or ""
    content = " ".join(str(item.get("content") or item.get("excerpt") or "").split())
    if len(content) > 700:
        content = content[:697].rstrip() + "..."
    meta = "; ".join(part for part in (
        f"source={source}" if source else "",
        f"hypothesis={hypothesis}" if hypothesis else "",
        f"tool={tool}" if tool else "",
        f"time={timestamp}" if timestamp else "",
    ) if part)
    return f"- {title} ({meta}): {content}"
