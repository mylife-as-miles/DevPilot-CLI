"""Search and prompt surfacing for learned local memory."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from .store import LearningStore
from .types import MemoryRecord, SkillRecord


def search_memories(
    project_root: str | Path,
    query: str,
    *,
    limit: int = 20,
    kind: str | None = None,
    tag: str | None = None,
) -> list[MemoryRecord]:
    needle = query.lower().strip()
    if not needle:
        return []
    records = LearningStore(project_root).list_memories(kind=kind, tag=tag)
    matches = [memory for memory in records if needle in _memory_haystack(memory)]
    return matches[-max(0, limit):]


def build_learned_memory_section(
    project_root: str | Path,
    *,
    query: str = "",
    hypothesis_id: str | None = None,
    max_memories: int = 5,
    max_skills: int = 3,
) -> str:
    store = LearningStore(project_root)
    memories = _rank_memories(store.list_memories(), query=query, hypothesis_id=hypothesis_id)[:max(0, max_memories)]
    skills = _rank_skills(store.list_skills(), query=query)[:max(0, max_skills)]
    if not memories and not skills:
        return ""

    lines = ["## DevPilot Learned Memory"]
    if memories:
        lines.extend(["", "Relevant local lessons:"])
        for memory in memories:
            lines.append(f"- {_memory_line(memory)}")
    if skills:
        lines.extend(["", "Relevant reusable skills:"])
        for skill in skills:
            lines.append(f"- {_skill_line(skill)}")
    return "\n".join(lines)


def _rank_memories(
    memories: Iterable[MemoryRecord],
    *,
    query: str,
    hypothesis_id: str | None,
) -> list[MemoryRecord]:
    terms = _terms(query)

    def score(memory: MemoryRecord) -> tuple[float, str]:
        text = _memory_haystack(memory)
        value = float(memory.get("confidence", 0.0) or 0.0)
        if hypothesis_id and memory.get("related_hypothesis_id") == hypothesis_id:
            value += 5.0
        for term in terms:
            if term in str(memory.get("title", "")).lower():
                value += 2.0
            if term in text:
                value += 1.0
        if not terms and not hypothesis_id:
            value += 0.5
        return (value, str(memory.get("created_at") or ""))

    ranked = sorted(memories, key=score, reverse=True)
    return [m for m in ranked if score(m)[0] > 0.0]


def _rank_skills(skills: Iterable[SkillRecord], *, query: str) -> list[SkillRecord]:
    terms = _terms(query)

    def score(skill: SkillRecord) -> tuple[float, str]:
        text = _skill_haystack(skill)
        value = float(skill.get("success_count", 0) or 0)
        for term in terms:
            if term in str(skill.get("name", "")).lower():
                value += 2.0
            if term in text:
                value += 1.0
        if not terms:
            value += 0.5
        return (value, str(skill.get("updated_at") or ""))

    ranked = sorted(skills, key=score, reverse=True)
    return [s for s in ranked if score(s)[0] > 0.0]


def _memory_line(memory: MemoryRecord) -> str:
    title = str(memory.get("title") or "Memory").strip()
    content = _compact(str(memory.get("content") or ""), 170)
    tags = ", ".join(str(t) for t in (memory.get("tags") or [])[:3])
    suffix = f" [{tags}]" if tags else ""
    return _compact(f"{title}: {content}{suffix}", 240)


def _skill_line(skill: SkillRecord) -> str:
    name = str(skill.get("name") or "skill").strip()
    trigger = _compact(str(skill.get("trigger") or skill.get("description") or ""), 120)
    procedure = skill.get("procedure") or []
    first_steps = "; ".join(str(step) for step in procedure[:2])
    detail = f"{trigger}. Steps: {first_steps}" if first_steps else trigger
    return _compact(f"{name}: {detail}", 260)


def _memory_haystack(memory: MemoryRecord) -> str:
    return " ".join([
        str(memory.get("title") or ""),
        str(memory.get("content") or ""),
        str(memory.get("source") or ""),
        " ".join(str(t) for t in memory.get("tags", []) or []),
    ]).lower()


def _skill_haystack(skill: SkillRecord) -> str:
    return " ".join([
        str(skill.get("name") or ""),
        str(skill.get("description") or ""),
        str(skill.get("trigger") or ""),
        " ".join(str(step) for step in skill.get("procedure", []) or []),
    ]).lower()


def _terms(query: str) -> list[str]:
    return [t for t in re.split(r"[^a-zA-Z0-9_]+", query.lower()) if len(t) >= 3][:12]


def _compact(text: str, limit: int) -> str:
    clean = re.sub(r"\s+", " ", text.strip())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 3)].rstrip() + "..."
