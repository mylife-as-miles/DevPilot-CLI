"""Heuristic memory extraction from completed DevPilot sessions."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
from typing import Any

from .session_reader import (
    read_executor_summaries,
    read_idea_tree,
    read_reach_evidence,
    read_report,
)
from .types import MemoryKind, MemoryRecord, MemorySource, make_id, utc_now_iso


SUCCESS_TERMS = (
    "improved",
    "success",
    "successful",
    "merged",
    "beat",
    "faster",
    "reduced",
    "validated",
    "passed",
    "best",
)
FAILURE_TERMS = (
    "failed",
    "failure",
    "did not improve",
    "didn't improve",
    "worse",
    "regression",
    "error",
    "timeout",
    "underperform",
    "hurt",
)
VECTOR_TERMS = ("vectorized", "vectorization", "numpy", "array loop", "hot loop")
VALIDATION_TERMS = ("b_dev", "b_test", "held-out", "validation", "test set", "compare against reference")
TOOL_TERMS = ("runtraining", "pytest", "reach", "grep", "glob", "bash", "uv run")


def extract_memories_from_session(
    session_dir: str | Path,
    project_root: str | Path,
) -> list[MemoryRecord]:
    """Extract compact, deterministic memories from a session directory."""
    session = Path(session_dir).resolve()
    project = Path(project_root).resolve()
    context = _Context(project_name=project.name, session_id=session.name)

    memories: list[MemoryRecord] = []
    memories.extend(_memories_from_report(read_report(session), context))
    memories.extend(_memories_from_evidence(read_reach_evidence(session), context))
    memories.extend(_memories_from_idea_tree(read_idea_tree(session), context))
    memories.extend(_memories_from_executors(read_executor_summaries(session), context))
    return _dedupe_memories(memories)


class _Context:
    def __init__(self, *, project_name: str | None, session_id: str):
        self.project_name = project_name
        self.session_id = session_id
        self.created_at = utc_now_iso()


def _mem(
    ctx: _Context,
    *,
    kind: MemoryKind,
    source: MemorySource,
    title: str,
    content: str,
    tags: list[str],
    confidence: float,
    related_hypothesis_id: str | None = None,
) -> MemoryRecord:
    clean_title = _compact(title, 90)
    clean_content = _compact(content, 500)
    return MemoryRecord(
        id=make_id(
            "mem",
            ctx.project_name,
            ctx.session_id,
            kind,
            source,
            clean_title,
            clean_content,
            related_hypothesis_id or "",
        ),
        kind=kind,
        project=ctx.project_name,
        session_id=ctx.session_id,
        source=source,
        title=clean_title,
        content=clean_content,
        tags=_clean_tags(tags),
        created_at=ctx.created_at,
        confidence=max(0.0, min(1.0, confidence)),
        related_hypothesis_id=related_hypothesis_id,
    )


def _memories_from_report(report: str, ctx: _Context) -> list[MemoryRecord]:
    if not report.strip():
        return []
    lower = report.lower()
    memories: list[MemoryRecord] = []

    if any(term in lower for term in VECTOR_TERMS):
        memories.append(_mem(
            ctx,
            kind="strategy",
            source="report",
            title="Vectorization improved a hot path",
            content=_first_excerpt(report, VECTOR_TERMS, fallback=report),
            tags=["optimization", "vectorization", "report"],
            confidence=0.86,
        ))

    if any(term in lower for term in VALIDATION_TERMS):
        memories.append(_mem(
            ctx,
            kind="strategy",
            source="report",
            title="Preserve validation discipline",
            content=_first_excerpt(report, VALIDATION_TERMS, fallback=report),
            tags=["validation", "benchmark", "report"],
            confidence=0.78,
        ))

    if any(term in lower for term in FAILURE_TERMS):
        memories.append(_mem(
            ctx,
            kind="failure",
            source="report",
            title="Failed or risky strategy recorded",
            content=_first_excerpt(report, FAILURE_TERMS, fallback=report),
            tags=["failure", "report"],
            confidence=0.72,
        ))

    if any(term in lower for term in SUCCESS_TERMS):
        memories.append(_mem(
            ctx,
            kind="lesson",
            source="report",
            title="Successful session strategy",
            content=_first_excerpt(report, SUCCESS_TERMS, fallback=report),
            tags=["success", "report"],
            confidence=0.75,
        ))

    if any(term in lower for term in TOOL_TERMS):
        memories.append(_mem(
            ctx,
            kind="tool_usage",
            source="report",
            title="Tool usage pattern from report",
            content=_first_excerpt(report, TOOL_TERMS, fallback=report),
            tags=["tooling", "report"],
            confidence=0.64,
        ))

    if not memories:
        memories.append(_mem(
            ctx,
            kind="lesson",
            source="report",
            title="Session report summary",
            content=_compact(_strip_markdown_noise(report), 500),
            tags=["report"],
            confidence=0.55,
        ))

    return memories


def _memories_from_evidence(records: list[dict[str, Any]], ctx: _Context) -> list[MemoryRecord]:
    memories: list[MemoryRecord] = []
    tool_counts: Counter[str] = Counter()
    for record in records[:30]:
        tool = str(record.get("tool") or "reach").strip()
        tool_counts[tool] += 1
        content = str(record.get("summary") or record.get("content") or "").strip()
        if not content:
            continue
        source = str(record.get("source") or record.get("query") or "evidence")
        title = str(record.get("title") or source).strip()
        lower = content.lower()
        kind: MemoryKind = "failure" if any(term in lower for term in FAILURE_TERMS) else "evidence"
        memories.append(_mem(
            ctx,
            kind=kind,
            source="evidence",
            title=f"Reach evidence: {title}",
            content=content,
            tags=["reach", _tagify(tool)],
            confidence=0.68 if kind == "evidence" else 0.62,
            related_hypothesis_id=_optional_str(record.get("hypothesis_id")),
        ))

    for tool, count in tool_counts.items():
        if count >= 2:
            memories.append(_mem(
                ctx,
                kind="tool_usage",
                source="evidence",
                title=f"Repeated Reach tool: {tool}",
                content=f"{tool} produced {count} evidence records in this session; consider it when similar evidence is needed.",
                tags=["reach", "tooling", _tagify(tool)],
                confidence=0.7,
            ))
    return memories


def _memories_from_idea_tree(tree: dict[str, Any], ctx: _Context) -> list[MemoryRecord]:
    nodes = tree.get("nodes") if isinstance(tree, dict) else None
    if not isinstance(nodes, dict):
        return []
    memories: list[MemoryRecord] = []
    for node_id, raw_node in nodes.items():
        if str(node_id).upper() == "ROOT" or not isinstance(raw_node, dict):
            continue
        status = str(raw_node.get("status") or "").lower()
        hypothesis = str(raw_node.get("hypothesis") or "").strip()
        insight = str(raw_node.get("insight") or raw_node.get("result") or "").strip()
        score = raw_node.get("score")
        body = ". ".join(part for part in [hypothesis, insight] if part)
        if not body:
            continue
        if status in {"merged", "done"}:
            score_s = f" with score {score}" if score is not None else ""
            memories.append(_mem(
                ctx,
                kind="lesson",
                source="idea_tree",
                title=f"Idea {node_id} {status}{score_s}",
                content=body,
                tags=["idea_tree", "success", status],
                confidence=0.86 if status == "merged" else 0.74,
                related_hypothesis_id=str(node_id),
            ))
        elif status in {"pruned", "failed", "needs_retry"}:
            memories.append(_mem(
                ctx,
                kind="failure",
                source="idea_tree",
                title=f"Idea {node_id} ended as {status}",
                content=body,
                tags=["idea_tree", "failure", status],
                confidence=0.74,
                related_hypothesis_id=str(node_id),
            ))
    return memories


def _memories_from_executors(records: list[dict[str, Any]], ctx: _Context) -> list[MemoryRecord]:
    memories: list[MemoryRecord] = []
    for record in records[:20]:
        report = str(record.get("report") or record.get("summary") or record.get("content") or "").strip()
        metrics = record.get("metrics") if isinstance(record.get("metrics"), dict) else {}
        node_id = _optional_str(record.get("node_id") or metrics.get("node_id"))
        status = str(metrics.get("status") or record.get("status") or "").lower()
        if not report and not metrics:
            continue
        lower = report.lower()
        failed = status in {"failed", "pruned", "needs_retry"} or any(term in lower for term in FAILURE_TERMS)
        kind: MemoryKind = "failure" if failed else "lesson"
        title_status = status or ("failed" if failed else "completed")
        content = report or f"Executor metrics: {metrics}"
        memories.append(_mem(
            ctx,
            kind=kind,
            source="executor_log",
            title=f"Executor {node_id or 'run'} {title_status}",
            content=content,
            tags=["executor", "failure" if failed else "success"],
            confidence=0.7 if failed else 0.73,
            related_hypothesis_id=node_id,
        ))
    return memories


def _dedupe_memories(memories: list[MemoryRecord]) -> list[MemoryRecord]:
    seen: set[str] = set()
    out: list[MemoryRecord] = []
    for memory in memories:
        key = "\0".join([
            memory.kind,
            memory.source,
            memory.title.lower(),
            memory.content.lower(),
            memory.related_hypothesis_id or "",
        ])
        if key in seen:
            continue
        seen.add(key)
        out.append(memory)
    return out


def _first_excerpt(text: str, terms: tuple[str, ...], *, fallback: str) -> str:
    lines = [line.strip(" -\t") for line in text.splitlines() if line.strip()]
    for line in lines:
        lower = line.lower()
        if any(term in lower for term in terms):
            return line
    sentences = re.split(r"(?<=[.!?])\s+", _strip_markdown_noise(text))
    for sentence in sentences:
        lower = sentence.lower()
        if any(term in lower for term in terms):
            return sentence
    return _strip_markdown_noise(fallback)


def _strip_markdown_noise(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        lines.append(stripped)
    return " ".join(lines)


def _compact(text: str, max_chars: int) -> str:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(clean) <= max_chars:
        return clean
    return clean[: max(0, max_chars - 3)].rstrip() + "..."


def _clean_tags(tags: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        clean = _tagify(tag)
        if clean and clean not in seen:
            seen.add(clean)
            out.append(clean)
    return out


def _tagify(value: object) -> str:
    text = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    return text[:40]


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
