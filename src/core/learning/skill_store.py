"""Convenience helpers for local learned skills."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .store import LearningStore
from .types import SkillRecord


def list_skills(project_root: str | Path, *, limit: int | None = None) -> list[SkillRecord]:
    return LearningStore(project_root).list_skills(limit=limit)


def get_skill(project_root: str | Path, skill_id: str) -> SkillRecord | None:
    return LearningStore(project_root).get_skill(skill_id)


def store_skills(project_root: str | Path, skills: Iterable[SkillRecord]) -> tuple[int, int]:
    store = LearningStore(project_root)
    store.ensure()
    created = 0
    skipped = 0
    for skill in skills:
        if store.append_skill(skill, dedupe=True):
            created += 1
        else:
            skipped += 1
    return created, skipped
