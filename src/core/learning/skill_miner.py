"""Deterministic skill mining from successful memories."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable

from .types import MemoryRecord, SkillRecord, make_id, utc_now_iso


def mine_skills_from_memories(memories: Iterable[MemoryRecord]) -> list[SkillRecord]:
    """Create compact skill candidates from repeated or high-confidence patterns."""
    memories = list(memories)
    successful = [m for m in memories if _field(m, "kind") != "failure"]
    candidates: list[SkillRecord] = []

    vector_memories = [
        m for m in successful
        if _contains_any(m, ("vectorized", "vectorization", "numpy", "array loop", "hot loop"))
        and (_float_field(m, "confidence") >= 0.7 or _count_pattern(successful, ("vectorized", "vectorization", "numpy")) >= 2)
    ]
    if vector_memories:
        candidates.append(_skill(
            name="optimize_numpy_hot_loop",
            description="When a benchmark bottleneck is a Python loop over arrays, try vectorization first.",
            trigger="Python benchmark has loops over numpy arrays",
            procedure=[
                "Profile the slow path",
                "Identify loop-carried dependencies",
                "Vectorize safely",
                "Compare against reference output",
                "Validate on held-out test split",
            ],
            memories=vector_memories,
        ))

    validation_memories = [
        m for m in successful
        if _contains_any(m, ("b_dev", "b_test", "held-out", "validation", "test set", "reference output"))
    ]
    if len(validation_memories) >= 1 and _max_conf(validation_memories) >= 0.72:
        candidates.append(_skill(
            name="preserve_validation_discipline",
            description="Keep fast iteration evidence separate from final validation and compare outputs before trusting a score.",
            trigger="A task has dev/test splits or benchmark-specific validation constraints",
            procedure=[
                "Identify the dev and final validation commands",
                "Run quick checks on the dev split first",
                "Compare outputs against a trusted reference",
                "Use the final test split only for merge or final decisions",
            ],
            memories=validation_memories,
        ))

    tool_memories_by_tag: dict[str, list[MemoryRecord]] = defaultdict(list)
    for memory in successful:
        if _field(memory, "kind") != "tool_usage":
            continue
        for tag in _field(memory, "tags", []) or []:
            if tag not in {"tooling", "report", "success"}:
                tool_memories_by_tag[tag].append(memory)
    for tag, tagged_memories in tool_memories_by_tag.items():
        if len(tagged_memories) < 1 or _max_conf(tagged_memories) < 0.65:
            continue
        clean = tag.replace("_", " ")
        candidates.append(_skill(
            name=f"use_{tag}_for_evidence",
            description=f"When similar evidence is needed, use {clean} early and preserve the result in session evidence.",
            trigger=f"Need local evidence that {clean} can collect or verify",
            procedure=[
                "State the exact evidence needed",
                f"Run {clean} with the smallest useful query or target",
                "Save or cite the evidence in the session",
                "Use the evidence to decide whether to continue, prune, or merge",
            ],
            memories=tagged_memories,
        ))

    recurring_tags = Counter(
        tag
        for memory in successful
        for tag in (_field(memory, "tags", []) or [])
        if tag not in {"report", "success", "failure", "idea_tree", "executor"}
    )
    for tag, count in recurring_tags.items():
        if count < 2:
            continue
        related = [m for m in successful if tag in (_field(m, "tags", []) or [])]
        candidates.append(_skill(
            name=f"reuse_{tag}_lesson",
            description=f"Reuse the recurring {tag.replace('_', ' ')} lesson when a future run has the same signal.",
            trigger=f"Task context mentions {tag.replace('_', ' ')} or similar constraints",
            procedure=[
                "Check whether the current task matches the prior signal",
                "Apply the smallest version of the learned tactic",
                "Measure against the run baseline",
                "Record whether the lesson still holds",
            ],
            memories=related,
        ))

    return _dedupe_skills(candidates)


def _skill(
    *,
    name: str,
    description: str,
    trigger: str,
    procedure: list[str],
    memories: list[MemoryRecord],
) -> SkillRecord:
    now = utc_now_iso()
    evidence = []
    for memory in memories:
        memory_id = str(_field(memory, "id", ""))
        if memory_id and memory_id not in evidence:
            evidence.append(memory_id)
    return SkillRecord(
        id=make_id("skill", name, trigger),
        name=name,
        description=description,
        trigger=trigger,
        procedure=procedure[:6],
        evidence=evidence[:10],
        success_count=max(1, len(memories)),
        failure_count=0,
        created_at=now,
        updated_at=now,
    )


def _dedupe_skills(skills: list[SkillRecord]) -> list[SkillRecord]:
    seen: set[str] = set()
    out: list[SkillRecord] = []
    for skill in skills:
        key = skill.name.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        out.append(skill)
    return out


def _contains_any(memory: MemoryRecord, terms: tuple[str, ...]) -> bool:
    text = " ".join([
        str(_field(memory, "title", "")),
        str(_field(memory, "content", "")),
        " ".join(str(t) for t in (_field(memory, "tags", []) or [])),
    ]).lower()
    return any(term in text for term in terms)


def _count_pattern(memories: list[MemoryRecord], terms: tuple[str, ...]) -> int:
    return sum(1 for memory in memories if _contains_any(memory, terms))


def _max_conf(memories: list[MemoryRecord]) -> float:
    return max((_float_field(m, "confidence") for m in memories), default=0.0)


def _field(record: object, key: str, default: object = None) -> object:
    if hasattr(record, "get"):
        return record.get(key, default)  # type: ignore[call-arg]
    return getattr(record, key, default)


def _float_field(record: object, key: str) -> float:
    try:
        return float(_field(record, key, 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0
