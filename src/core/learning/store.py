"""Append-only JSONL stores for project-local learning data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from ..._app import CONFIG_DIR_NAME
from .types import MemoryRecord, SkillRecord, TrajectoryRecord


def resolve_learning_project_root(cwd: str | Path, workspace_dir: str | Path | None = None) -> Path:
    if workspace_dir:
        workspace = Path(workspace_dir).expanduser().resolve()
        if workspace.parent.name == "sessions" and workspace.parent.parent.name == CONFIG_DIR_NAME:
            return workspace.parent.parent.parent.resolve()
        for parent in workspace.parents:
            if parent.name == CONFIG_DIR_NAME:
                return parent.parent.resolve()
    return Path(cwd).expanduser().resolve()


def infer_project_root_from_session(session_dir: str | Path) -> Path:
    session_path = Path(session_dir).expanduser().resolve()
    if session_path.parent.name == "sessions" and session_path.parent.parent.name == CONFIG_DIR_NAME:
        return session_path.parent.parent.parent.resolve()
    return session_path.parent.resolve()


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


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


class LearningStore:
    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).expanduser().resolve()
        self.devpilot_dir = self.project_root / CONFIG_DIR_NAME
        self.memory_dir = self.devpilot_dir / "memory"
        self.memories_path = self.memory_dir / "memories.jsonl"
        self.skills_path = self.memory_dir / "skills.jsonl"
        self.trajectories_path = self.memory_dir / "trajectories.jsonl"

    def ensure(self) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        for path in (self.memories_path, self.skills_path, self.trajectories_path):
            path.touch(exist_ok=True)

    def is_project_local(self) -> bool:
        try:
            self.memory_dir.relative_to(self.project_root)
        except ValueError:
            return False
        return self.devpilot_dir.name == CONFIG_DIR_NAME

    def check_writable(self) -> bool:
        self.ensure()
        probe = self.memory_dir / ".write_test"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    def list_memories(
        self,
        *,
        limit: int | None = None,
        kind: str | None = None,
        tag: str | None = None,
    ) -> list[MemoryRecord]:
        records = [r for r in read_jsonl(self.memories_path) if isinstance(r.get("id"), str)]
        if kind:
            records = [r for r in records if r.get("kind") == kind]
        if tag:
            needle = tag.lower()
            records = [
                r for r in records
                if any(str(t).lower() == needle for t in r.get("tags", []) or [])
            ]
        if limit is not None:
            records = records[-max(0, limit):]
        return records  # type: ignore[return-value]

    def list_skills(self, *, limit: int | None = None) -> list[SkillRecord]:
        records = [r for r in read_jsonl(self.skills_path) if isinstance(r.get("id"), str)]
        if limit is not None:
            records = records[-max(0, limit):]
        return records  # type: ignore[return-value]

    def list_trajectories(self, *, limit: int | None = None) -> list[TrajectoryRecord]:
        records = [r for r in read_jsonl(self.trajectories_path) if isinstance(r.get("id"), str)]
        if limit is not None:
            records = records[-max(0, limit):]
        return records  # type: ignore[return-value]

    def append_memory(self, record: MemoryRecord, *, dedupe: bool = True) -> bool:
        data = _record_dict(record)
        if dedupe and self._has_id(self.memories_path, str(data.get("id", ""))):
            return False
        append_jsonl(self.memories_path, data)
        return True

    def append_memories(self, records: Iterable[MemoryRecord], *, dedupe: bool = True) -> int:
        return sum(1 for record in records if self.append_memory(record, dedupe=dedupe))

    def append_skill(self, record: SkillRecord, *, dedupe: bool = True) -> bool:
        data = _record_dict(record)
        if dedupe and self._has_duplicate_skill(data):
            return False
        append_jsonl(self.skills_path, data)
        return True

    def append_skills(self, records: Iterable[SkillRecord], *, dedupe: bool = True) -> int:
        return sum(1 for record in records if self.append_skill(record, dedupe=dedupe))

    def append_trajectory(self, record: TrajectoryRecord, *, dedupe: bool = True) -> bool:
        data = _record_dict(record)
        if dedupe and self._has_id(self.trajectories_path, str(data.get("id", ""))):
            return False
        append_jsonl(self.trajectories_path, data)
        return True

    def get_skill(self, skill_id: str) -> SkillRecord | None:
        for skill in self.list_skills():
            if skill.get("id") == skill_id:
                return skill
        return None

    def _has_id(self, path: Path, record_id: str) -> bool:
        if not record_id:
            return False
        return any(r.get("id") == record_id for r in read_jsonl(path))

    def _has_duplicate_skill(self, record: SkillRecord) -> bool:
        record_id = record.get("id")
        record_name = str(record.get("name") or "").strip().lower()
        record_trigger = str(record.get("trigger") or "").strip().lower()
        for existing in read_jsonl(self.skills_path):
            if record_id and existing.get("id") == record_id:
                return True
            if record_name and str(existing.get("name") or "").strip().lower() == record_name:
                return True
            if record_trigger and str(existing.get("trigger") or "").strip().lower() == record_trigger:
                return True
        return False


def _record_dict(record: Any) -> dict[str, Any]:
    if hasattr(record, "to_dict"):
        data = record.to_dict()
        return data if isinstance(data, dict) else {}
    if isinstance(record, dict):
        return dict(record)
    return dict(record)
