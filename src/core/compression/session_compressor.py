"""Compress DevPilot session artifacts into traceable markdown summaries."""

from __future__ import annotations

from pathlib import Path

from ..._app import CONFIG_DIR_NAME
from .evidence_compressor import read_jsonl, resolve_session_dir
from .runner import append_manifest, conservative_compress_text, ensure_compression_workspace, reports_dir
from .types import CompressionArtifact


def compress_session(
    project_root: str | Path,
    session: str | None = None,
    *,
    max_chars: int = 8000,
) -> CompressionArtifact:
    root = Path(project_root).resolve()
    session_dir = resolve_session_dir(root, session)
    if session_dir is None:
        return CompressionArtifact(path=None, message="No sessions found in .devpilot/sessions/.")

    rendered = render_session_markdown(root, session_dir)
    compressed = conservative_compress_text(rendered, max_chars=max_chars)
    ensure_compression_workspace(root)
    out = reports_dir(root) / f"{session_dir.name}.compressed.md"
    out.write_text(compressed + "\n", encoding="utf-8")
    append_manifest(root, {"action": "session", "session_id": session_dir.name, "output": str(out)})
    return CompressionArtifact(path=out, content=compressed, source_count=1, message=f"Compressed session {session_dir.name}.")


def compress_logs(
    project_root: str | Path,
    session: str | None = None,
    *,
    max_chars: int = 6000,
) -> CompressionArtifact:
    root = Path(project_root).resolve()
    session_dir = resolve_session_dir(root, session)
    if session_dir is None:
        return CompressionArtifact(path=None, message="No sessions found in .devpilot/sessions/.")

    logs = _collect_logs(session_dir)
    if not logs:
        return CompressionArtifact(path=None, message=f"No logs found for session {session_dir.name}.")
    lines = [f"# Compressed Logs: {session_dir.name}", ""]
    for label, text in logs:
        lines.append(f"## {label}")
        lines.append(_log_excerpt(text))
        lines.append("")
    compressed = conservative_compress_text("\n".join(lines), max_chars=max_chars)
    ensure_compression_workspace(root)
    out = reports_dir(root) / f"{session_dir.name}.logs.compressed.md"
    out.write_text(compressed + "\n", encoding="utf-8")
    append_manifest(root, {"action": "logs", "session_id": session_dir.name, "files": len(logs), "output": str(out)})
    return CompressionArtifact(path=out, content=compressed, source_count=len(logs), message=f"Compressed {len(logs)} log file(s).")


def render_session_markdown(project_root: Path, session_dir: Path) -> str:
    lines = [f"# DevPilot Session Compression: {session_dir.name}", ""]
    report = _safe_read(session_dir / "REPORT.md")
    if report:
        lines.extend(["## Final Report Summary", report[:6000], ""])

    evidence = read_jsonl(session_dir / "reach_evidence.jsonl")
    if evidence:
        lines.append("## Evidence Sources")
        for item in evidence[:40]:
            source = item.get("source") or item.get("url") or ""
            hypo = item.get("hypothesis_id") or ""
            title = item.get("title") or source or "Evidence"
            content = " ".join(str(item.get("content") or "").split())[:300]
            lines.append(f"- {title} source={source} hypothesis={hypo}: {content}")
        lines.append("")

    for name in ("memories.jsonl", "skills.jsonl", "trajectories.jsonl"):
        records = read_jsonl(project_root / CONFIG_DIR_NAME / "memory" / name)
        if records:
            lines.append(f"## {name}")
            for record in records[-20:]:
                title = record.get("title") or record.get("name") or record.get("id")
                content = record.get("content") or record.get("description") or record.get("summary") or ""
                lines.append(f"- {title}: {' '.join(str(content).split())[:300]}")
            lines.append("")

    logs = _collect_logs(session_dir)
    if logs:
        lines.append("## Log Highlights")
        for label, text in logs[:5]:
            lines.append(f"### {label}")
            lines.append(_log_excerpt(text, limit=1200))
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def _collect_logs(session_dir: Path) -> list[tuple[str, str]]:
    candidates: list[Path] = []
    for pattern in ("*.log", "*log*.txt", "events.jsonl", "COORDINATOR_FINAL_REPORT.txt"):
        candidates.extend(session_dir.rglob(pattern))
    seen: set[Path] = set()
    logs: list[tuple[str, str]] = []
    for path in candidates:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        text = _safe_read(path)
        if text:
            logs.append((str(path.relative_to(session_dir)), text))
    return logs


def _log_excerpt(text: str, *, limit: int = 1800) -> str:
    useful: list[str] = []
    patterns = ("failed", "failure", "error", "traceback", "assert", "test_", "exit code", "command")
    lines = text.splitlines()
    for line in lines:
        lower = line.lower()
        if any(pattern in lower for pattern in patterns):
            useful.append(line.rstrip())
    if not useful:
        useful = [line.rstrip() for line in lines[-40:]]
    excerpt = "\n".join(useful)
    if len(excerpt) <= limit:
        return excerpt
    return excerpt[: limit - 14].rstrip() + "\n\n[truncated]"


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
