from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from devpilot.cli.app import app
from devpilot.cli.commands.learn_cmd import learn_app
from devpilot.core.learning.memory import extract_memories_from_session
from devpilot.core.learning.search import build_learned_memory_section, search_memories
from devpilot.core.learning.session_reader import (
    read_executor_summaries,
    read_idea_tree,
    read_reach_evidence,
    read_report,
)
from devpilot.core.learning.skill_miner import mine_skills_from_memories
from devpilot.core.learning.store import LearningStore
from devpilot.core.learning.trajectory import compress_session_trajectory
from devpilot.core.learning.types import MemoryRecord, stable_id, utc_now_iso


runner = CliRunner()


def test_learn_help() -> None:
    result = runner.invoke(app, ["learn", "--help"])
    assert result.exit_code == 0
    assert "Local DevPilot learning" in result.output


def test_learn_doctor(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(learn_app, ["doctor"])
    assert result.exit_code == 0
    assert "OK package imports work" in result.output
    assert (tmp_path / ".devpilot" / "memory" / "memories.jsonl").exists()


def test_memory_store_append_list_search(tmp_path: Path) -> None:
    store = LearningStore(tmp_path)
    store.ensure()
    memory = _memory("Vectorization worked", "Vectorized numpy loop improved the benchmark", tags=["optimization"])

    assert store.append_memory(memory) is True
    assert store.append_memory(memory) is False
    assert store.list_memories()[0]["id"] == memory["id"]
    assert search_memories(tmp_path, "NUMPY")[0]["title"] == "Vectorization worked"


def test_malformed_jsonl_skipped_gracefully(tmp_path: Path) -> None:
    store = LearningStore(tmp_path)
    store.ensure()
    good = _memory("Good", "Readable memory")
    store.memories_path.write_text(
        json.dumps(good) + "\nnot-json\n" + json.dumps(_memory("Also good", "Readable too")) + "\n",
        encoding="utf-8",
    )

    records = store.list_memories()
    assert len(records) == 2
    assert {r["title"] for r in records} == {"Good", "Also good"}


def test_session_reader_handles_missing_files(tmp_path: Path) -> None:
    session = tmp_path / "missing"
    session.mkdir()

    assert read_report(session) == ""
    assert read_reach_evidence(session) == []
    assert read_idea_tree(session) == {}
    assert read_executor_summaries(session) == []


def test_memory_extraction_from_fake_report(tmp_path: Path) -> None:
    session = tmp_path / ".devpilot" / "sessions" / "s1"
    session.mkdir(parents=True)
    (session / "REPORT.md").write_text(
        "# Research Report\n\n- Vectorized the numpy hot loop and improved benchmark throughput.\n",
        encoding="utf-8",
    )

    memories = extract_memories_from_session(session, tmp_path)
    assert any(m["kind"] == "strategy" and "Vectorization" in m["title"] for m in memories)
    assert any("optimization" in m["tags"] for m in memories)


def test_memory_extraction_from_fake_reach_evidence(tmp_path: Path) -> None:
    session = tmp_path / ".devpilot" / "sessions" / "s2"
    session.mkdir(parents=True)
    (session / "reach_evidence.jsonl").write_text(
        json.dumps({
            "tool": "reach_search",
            "source": "web_search",
            "title": "Benchmark note",
            "content": "Validation requires a held-out split.",
            "hypothesis_id": "n3",
        }) + "\n",
        encoding="utf-8",
    )

    memories = extract_memories_from_session(session, tmp_path)
    assert len(memories) == 1
    assert memories[0]["kind"] == "evidence"
    assert memories[0]["related_hypothesis_id"] == "n3"
    assert "reach_search" in memories[0]["tags"]


def test_skill_mining_from_repeated_successful_patterns() -> None:
    memories = [
        _memory("Vectorized path", "Vectorized numpy arrays improved the hot path", confidence=0.8),
        _memory("Numpy loop", "A vectorizable numpy hot path was faster after vectorization", confidence=0.75),
    ]

    skills = mine_skills_from_memories(memories)
    assert any(skill["name"] == "optimize_numpy_hot_loop" for skill in skills)
    skill = next(skill for skill in skills if skill["name"] == "optimize_numpy_hot_loop")
    assert skill["success_count"] == 2
    assert len(skill["procedure"]) <= 7


def test_duplicate_skill_prevention(tmp_path: Path) -> None:
    store = LearningStore(tmp_path)
    store.ensure()
    skill = mine_skills_from_memories([
        _memory("Vectorized path", "Vectorized numpy arrays improved the hot path", confidence=0.9)
    ])[0]

    assert store.append_skill(skill) is True
    assert store.append_skill(skill) is False
    assert len(store.list_skills()) == 1


def test_trajectory_compression_output(tmp_path: Path) -> None:
    session = tmp_path / ".devpilot" / "sessions" / "s3"
    (session / ".coordinator").mkdir(parents=True)
    (session / "REPORT.md").write_text("# Research Report: Speed run\n", encoding="utf-8")
    (session / ".coordinator" / "idea_tree.json").write_text(
        json.dumps({
            "meta": {"baseline_score": 1.0, "trunk_score": 1.3},
            "nodes": {
                "ROOT": {"status": "done"},
                "n1": {"status": "merged", "hypothesis": "Vectorize loop", "insight": "Faster", "score": 1.3},
                "n2": {"status": "pruned", "hypothesis": "Cache all", "prune_reason": "Memory too high"},
            },
        }),
        encoding="utf-8",
    )

    trajectory = compress_session_trajectory(session)
    assert trajectory["session_id"] == "s3"
    assert "Speed run" in trajectory["summary"]
    assert trajectory["successful_paths"]
    assert trajectory["failed_paths"]
    assert trajectory["key_decisions"]


def test_prompt_context_truncates_safely(tmp_path: Path) -> None:
    store = LearningStore(tmp_path)
    store.ensure()
    for i in range(10):
        store.append_memory(_memory(f"Memory {i}", "vectorized numpy hot path " + ("x" * 500), confidence=0.9))
    for skill in mine_skills_from_memories(store.list_memories()[:2]):
        store.append_skill(skill)

    section = build_learned_memory_section(tmp_path, query="vectorized numpy", max_memories=5, max_skills=3)
    assert "## DevPilot Learned Memory" in section
    assert section.count("- ") <= 8
    assert len(section) < 2500


def test_no_global_storage_is_used(tmp_path: Path) -> None:
    store = LearningStore(tmp_path)
    store.ensure()
    assert store.memory_dir == tmp_path.resolve() / ".devpilot" / "memory"
    assert store.is_project_local()


def _memory(
    title: str,
    content: str,
    *,
    tags: list[str] | None = None,
    confidence: float = 0.7,
) -> MemoryRecord:
    now = utc_now_iso()
    return {
        "id": stable_id("mem", title, content),
        "kind": "lesson",
        "project": "proj",
        "session_id": "s",
        "source": "report",
        "title": title,
        "content": content,
        "tags": tags or [],
        "created_at": now,
        "confidence": confidence,
        "related_hypothesis_id": None,
    }
