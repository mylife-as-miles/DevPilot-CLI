"""Deterministic trajectory compression for DevPilot sessions."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .memory import extract_memories_from_session
from .session_reader import read_idea_tree, read_reach_evidence, read_report, read_run_info
from .types import TrajectoryRecord, make_id, utc_now_iso


def compress_session_trajectory(session_dir: str | Path) -> TrajectoryRecord:
    session = Path(session_dir).resolve()
    run_info = read_run_info(session)
    project_root = _project_root_from_session(session, run_info)
    memories = extract_memories_from_session(session, project_root)
    report = read_report(session)
    tree = read_idea_tree(session)
    evidence = read_reach_evidence(session)

    summary = _session_summary(session, report, run_info, tree)
    key_decisions = _key_decisions(report, tree)
    failed_paths = [
        _compact(m.content, 180) for m in memories
        if m.kind == "failure"
    ][:8]
    successful_paths = [
        _compact(m.content, 180) for m in memories
        if m.kind in {"lesson", "strategy", "decision"} and "success" in m.tags
    ][:8]
    important_evidence = _important_evidence(evidence)
    reusable_lessons = [
        f"{m.title}: {_compact(m.content, 150)}"
        for m in memories
        if m.kind in {"lesson", "strategy", "tool_usage"}
    ][:8]

    return TrajectoryRecord(
        id=make_id("traj", session.name, summary, "|".join(reusable_lessons)),
        session_id=session.name,
        summary=summary,
        key_decisions=key_decisions,
        failed_paths=failed_paths,
        successful_paths=successful_paths,
        important_evidence=important_evidence,
        reusable_lessons=reusable_lessons,
        created_at=utc_now_iso(),
    )


def _project_root_from_session(session: Path, run_info: dict[str, Any]) -> Path:
    cwd = run_info.get("cwd")
    if cwd:
        try:
            return Path(str(cwd)).resolve()
        except OSError:
            pass
    if session.parent.name == "sessions" and session.parent.parent.name == ".devpilot":
        return session.parent.parent.parent.resolve()
    return session.parent.resolve()


def _session_summary(
    session: Path,
    report: str,
    run_info: dict[str, Any],
    tree: dict[str, Any],
) -> str:
    task = str(run_info.get("task") or "").strip()
    if not task and report:
        for line in report.splitlines():
            clean = line.strip("# ").strip()
            if clean:
                task = clean
                break
    if not task:
        task = f"Session {session.name}"

    meta = tree.get("meta") if isinstance(tree, dict) else {}
    if isinstance(meta, dict):
        baseline = meta.get("baseline_score")
        trunk = meta.get("trunk_score")
        if baseline is not None or trunk is not None:
            return _compact(f"{task}. Baseline={baseline}; final={trunk}.", 260)
    return _compact(task, 260)


def _key_decisions(report: str, tree: dict[str, Any]) -> list[str]:
    decisions: list[str] = []
    nodes = tree.get("nodes") if isinstance(tree, dict) else None
    if isinstance(nodes, dict):
        for node_id, raw_node in nodes.items():
            if str(node_id).upper() == "ROOT" or not isinstance(raw_node, dict):
                continue
            status = str(raw_node.get("status") or "").lower()
            if status in {"merged", "pruned"}:
                hypothesis = _compact(str(raw_node.get("hypothesis") or ""), 130)
                decisions.append(f"{status}: {node_id} {hypothesis}".strip())
    for line in report.splitlines():
        clean = line.strip(" -\t")
        lower = clean.lower()
        if clean and any(term in lower for term in ("decided", "chose", "merged", "pruned")):
            decisions.append(_compact(clean, 180))
    return _unique(decisions)[:10]


def _important_evidence(records: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for record in records[:10]:
        title = record.get("title") or record.get("source") or record.get("query")
        content = record.get("summary") or record.get("content") or ""
        if title or content:
            out.append(_compact(f"{title}: {content}", 180))
    return out[:8]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _compact(text: str, max_chars: int) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 3].rstrip() + "..."
