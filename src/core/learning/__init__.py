"""Local learning layer for DevPilot.

Phase 1 is deliberately local and deterministic: it reads completed session
artifacts, extracts compact memories, mines small reusable skills, and stores
append-only JSONL records under the active project's ``.devpilot/memory``.
"""

from .memory import extract_memories_from_session
from .skill_miner import mine_skills_from_memories
from .trajectory import compress_session_trajectory
from .types import MemoryRecord, SkillRecord, TrajectoryRecord

__all__ = [
    "MemoryRecord",
    "SkillRecord",
    "TrajectoryRecord",
    "compress_session_trajectory",
    "extract_memories_from_session",
    "mine_skills_from_memories",
]
