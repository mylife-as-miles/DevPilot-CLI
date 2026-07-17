"""Typed records used by the DevPilot Learning Layer."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Any, Literal
from uuid import uuid4


MemoryKind = Literal["lesson", "failure", "strategy", "tool_usage", "evidence", "decision"]
MemorySource = Literal["report", "evidence", "idea_tree", "executor_log", "manual"]


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp with a trailing Z."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def make_id(prefix: str, *seed_parts: object) -> str:
    """Create a compact record id."""
    if seed_parts:
        h = hashlib.sha1()
        for part in seed_parts:
            h.update(str(part).encode("utf-8", errors="replace"))
            h.update(b"\0")
        suffix = h.hexdigest()[:12]
    else:
        suffix = uuid4().hex[:12]
    return f"{prefix}_{suffix}"


def stable_id(prefix: str, *parts: object) -> str:
    """Backward-compatible stable id helper for tests and JSONL records."""
    return make_id(prefix, *parts)


def normalize_tags(tags: list[str] | tuple[str, ...]) -> list[str]:
    """Normalize tags for compact search and prompt surfaces."""
    out: list[str] = []
    for tag in tags:
        clean = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(tag).strip())
        clean = "_".join(part for part in clean.split("_") if part)
        if clean and clean not in out:
            out.append(clean)
    return out[:8]


@dataclass(slots=True)
class MemoryRecord:
    id: str
    kind: MemoryKind
    project: str | None
    session_id: str
    source: MemorySource
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    confidence: float = 0.0
    related_hypothesis_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryRecord":
        tags = data.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]
        return cls(
            id=str(data.get("id") or make_id("mem")),
            kind=_coerce_memory_kind(data.get("kind")),
            project=_none_or_str(data.get("project")),
            session_id=str(data.get("session_id") or ""),
            source=_coerce_memory_source(data.get("source")),
            title=str(data.get("title") or "Untitled memory"),
            content=str(data.get("content") or ""),
            tags=[str(t) for t in tags if str(t).strip()],
            created_at=str(data.get("created_at") or utc_now_iso()),
            confidence=_coerce_float(data.get("confidence"), default=0.0),
            related_hypothesis_id=_none_or_str(data.get("related_hypothesis_id")),
        )


@dataclass(slots=True)
class SkillRecord:
    id: str
    name: str
    description: str
    trigger: str
    procedure: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    success_count: int = 1
    failure_count: int = 0
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillRecord":
        procedure = data.get("procedure") or []
        evidence = data.get("evidence") or []
        if not isinstance(procedure, list):
            procedure = [str(procedure)]
        if not isinstance(evidence, list):
            evidence = [str(evidence)]
        name = str(data.get("name") or "learned_skill")
        trigger = str(data.get("trigger") or "")
        return cls(
            id=str(data.get("id") or make_id("skill", name, trigger)),
            name=name,
            description=str(data.get("description") or ""),
            trigger=trigger,
            procedure=[str(step) for step in procedure if str(step).strip()],
            evidence=[str(item) for item in evidence if str(item).strip()],
            success_count=_coerce_int(data.get("success_count"), default=1),
            failure_count=_coerce_int(data.get("failure_count"), default=0),
            created_at=str(data.get("created_at") or utc_now_iso()),
            updated_at=str(data.get("updated_at") or utc_now_iso()),
        )


@dataclass(slots=True)
class TrajectoryRecord:
    id: str
    session_id: str
    summary: str
    key_decisions: list[str] = field(default_factory=list)
    failed_paths: list[str] = field(default_factory=list)
    successful_paths: list[str] = field(default_factory=list)
    important_evidence: list[str] = field(default_factory=list)
    reusable_lessons: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TrajectoryRecord":
        summary = str(data.get("summary") or "")
        session_id = str(data.get("session_id") or "")
        return cls(
            id=str(data.get("id") or make_id("traj", session_id, summary)),
            session_id=session_id,
            summary=summary,
            key_decisions=_list_of_str(data.get("key_decisions")),
            failed_paths=_list_of_str(data.get("failed_paths")),
            successful_paths=_list_of_str(data.get("successful_paths")),
            important_evidence=_list_of_str(data.get("important_evidence")),
            reusable_lessons=_list_of_str(data.get("reusable_lessons")),
            created_at=str(data.get("created_at") or utc_now_iso()),
        )


def _list_of_str(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    return [str(value)]


def _none_or_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_float(value: object, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: object, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_memory_kind(value: object) -> MemoryKind:
    allowed = {"lesson", "failure", "strategy", "tool_usage", "evidence", "decision"}
    text = str(value or "lesson")
    return text if text in allowed else "lesson"  # type: ignore[return-value]


def _coerce_memory_source(value: object) -> MemorySource:
    allowed = {"report", "evidence", "idea_tree", "executor_log", "manual"}
    text = str(value or "manual")
    return text if text in allowed else "manual"  # type: ignore[return-value]
