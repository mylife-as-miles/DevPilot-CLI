"""Render REPORT.md from a finished session directory.

Inputs (any may be missing — partial reports are still useful):
  <session>/run_stats.json           orchestrator-written stats
  <session>/.coordinator/idea_tree.json   idea tree
  <session>/events.jsonl             EventBus log
  <session>/run_info.json            (optional, written by CLI)

Output:
  <session>/REPORT.md

No Jinja2 — deliberate, per plan §8.1. Plain string concatenation; if the
report grows complex enough to warrant templates, swap later.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..events.subscribers.stats_collector import EventStats


def generate_report(
    session_dir: Path,
    *,
    instruction: str | None = None,
    event_stats: EventStats | None = None,
    exit_reason: str = "ok",
    project_root: Path | None = None,
) -> Path:
    """Write REPORT.md and return its path. Never raises on missing data."""
    session_dir = Path(session_dir).resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    learning_project_root = Path(project_root).resolve() if project_root else _infer_learning_project_root(session_dir)

    run_stats = _load_json(session_dir / "run_stats.json")
    tree = _load_json(session_dir / ".coordinator" / "idea_tree.json")
    run_info = _load_json(session_dir / "run_info.json")

    parts: list[str] = []
    parts.append(_render_header(instruction, run_stats, run_info, exit_reason))
    parts.append(_render_event_summary(event_stats))
    parts.append(_render_run_stats(run_stats))
    parts.append(_render_results(tree))
    parts.append(_render_idea_tree(tree))
    parts.append(_render_reach_evidence(session_dir))
    parts.append(_render_learned_memory(session_dir, learning_project_root))
    parts.append(_render_artifacts(session_dir))

    body = "\n\n".join(p for p in parts if p)
    out_path = session_dir / "REPORT.md"
    out_path.write_text(body + "\n", encoding="utf-8")
    return out_path


# ── Sections ────────────────────────────────────────────────────────


def _render_header(
    instruction: str | None,
    run_stats: dict,
    run_info: dict,
    exit_reason: str,
) -> str:
    title = (instruction or run_info.get("task") or "Research session").strip().splitlines()[0]
    if len(title) > 100:
        title = title[:97] + "..."

    lines = [f"# Research Report: {title}", ""]
    when = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"_Generated {when}_   _Exit: `{exit_reason}`_")
    if instruction:
        lines.append("")
        lines.append("## Instruction")
        lines.append("")
        lines.append("> " + instruction.replace("\n", "\n> "))

    if run_stats.get("model"):
        lines.append("")
        lines.append(f"**Model**: `{run_stats['model']}`")
    if run_stats.get("duration_human"):
        lines.append(f"**Duration**: {run_stats['duration_human']}")
    return "\n".join(lines)


def _render_event_summary(stats: EventStats | None) -> str:
    if stats is None:
        return ""
    lines = ["## Event Summary", ""]
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Cycles completed | {stats.cycles} |")
    lines.append(f"| Ideas proposed | {stats.ideas_proposed} |")
    lines.append(f"| Ideas completed | {stats.ideas_completed} |")
    lines.append(f"| Ideas pruned | {stats.ideas_pruned} |")
    lines.append(f"| Ideas merged | {stats.ideas_merged} |")
    lines.append(f"| Sub-agent runs | {stats.executor_runs} |")
    lines.append(f"| LLM errors | {stats.llm_errors} |")
    lines.append(f"| Eval failures | {stats.eval_failures} |")
    if stats.session_duration_s is not None:
        lines.append(f"| Wall clock | {_fmt_duration(stats.session_duration_s)} |")
    return "\n".join(lines)


def _render_run_stats(stats: dict) -> str:
    if not stats:
        return ""
    all_a = stats.get("all_agents", {}) or {}
    meta_a = stats.get("coordinator", {}) or {}
    lines = ["## Run Stats", ""]
    if stats.get("token_scope"):
        lines.append(f"_Token scope_: `{stats['token_scope']}`")
        lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total LLM calls | {_fmt_int(all_a.get('total_llm_calls'))} |")
    lines.append(f"| Total agents spawned | {_fmt_int(all_a.get('total_agents_spawned'))} |")
    lines.append(f"| Total input tokens | {_fmt_int(all_a.get('total_input_tokens'))} |")
    if all_a.get("total_uncached_input_tokens") is not None:
        lines.append(f"| Total uncached input tokens | {_fmt_int(all_a.get('total_uncached_input_tokens'))} |")
    if all_a.get("total_cache_read_tokens"):
        lines.append(f"| Total cache-read input tokens | {_fmt_int(all_a.get('total_cache_read_tokens'))} |")
    if all_a.get("total_cache_creation_tokens"):
        lines.append(f"| Total cache-creation input tokens | {_fmt_int(all_a.get('total_cache_creation_tokens'))} |")
    lines.append(f"| Total output tokens | {_fmt_int(all_a.get('total_output_tokens'))} |")
    lines.append(f"| Coordinator turns | {_fmt_int(meta_a.get('turns'))} |")
    if stats.get("emergency_timeout"):
        lines.append("| Emergency timeout | yes |")
    return "\n".join(lines)


def _render_results(tree: dict) -> str:
    if not tree:
        return ""
    meta = tree.get("meta", {})
    bl = meta.get("baseline_score")
    tr = meta.get("trunk_score")
    if bl is None and tr is None:
        return ""

    lines = ["## Results", ""]
    if bl is not None and tr is not None:
        try:
            delta = tr - bl
            pct = (delta / bl * 100.0) if bl else None
            pct_s = f"{pct:+.2f}%" if pct is not None else "n/a"
            lines.append(f"**Baseline → Final**: `{bl:.4f}` → `{tr:.4f}` ({pct_s})")
        except (TypeError, ValueError):
            lines.append(f"**Baseline / Final**: `{bl}` / `{tr}`")
    else:
        if bl is not None:
            lines.append(f"**Baseline**: `{bl}`")
        if tr is not None:
            lines.append(f"**Final**: `{tr}`")

    test_bl = meta.get("test_baseline_score")
    test_tr = meta.get("test_trunk_score")
    if test_bl is not None or test_tr is not None:
        lines.append("")
        lines.append(f"**Test set**: baseline=`{test_bl}` final=`{test_tr}`")
    return "\n".join(lines)


def _render_idea_tree(tree: dict) -> str:
    if not tree:
        return ""
    nodes = tree.get("nodes", {}) or {}
    if not nodes:
        return ""

    # Pull merged + best ideas (top by score)
    scored: list[tuple[str, float, dict]] = []
    merged: list[tuple[str, dict]] = []
    for nid, node in nodes.items():
        score = node.get("score")
        if isinstance(score, (int, float)):
            scored.append((nid, float(score), node))
        if node.get("status") == "merged":
            merged.append((nid, node))

    scored.sort(key=lambda x: -x[1])
    lines = ["## Exploration", ""]
    lines.append(f"_{len(nodes)} nodes total, {len(scored)} scored, {len(merged)} merged_")

    if merged:
        lines.append("")
        lines.append("### Merged Ideas")
        lines.append("")
        for nid, node in merged:
            score = node.get("score")
            score_s = f"`{score}`" if score is not None else "_(no score)_"
            hypo = (node.get("hypothesis") or "").strip().splitlines()[0]
            lines.append(f"- **{nid}** ({score_s}): {hypo}")

    if scored:
        lines.append("")
        lines.append("### Top Ideas by Score")
        lines.append("")
        for nid, score, node in scored[:10]:
            hypo = (node.get("hypothesis") or "").strip().splitlines()[0]
            status = node.get("status", "?")
            lines.append(f"- **{nid}** `{score:.4f}` _{status}_: {hypo}")

    return "\n".join(lines)


def _render_artifacts(session_dir: Path) -> str:
    lines = ["## Artifacts", ""]
    candidates = [
        ("Coordinator final report", session_dir / "COORDINATOR_FINAL_REPORT.txt"),
        ("Interactive Q&A transcript", session_dir / "conversation.md"),
        ("Idea tree (JSON)", session_dir / ".coordinator" / "idea_tree.json"),
        ("Idea tree (Markdown)", session_dir / ".coordinator" / "idea_tree.md"),
        ("Run stats", session_dir / "run_stats.json"),
        ("Event log", session_dir / "events.jsonl"),
    ]
    for label, path in candidates:
        if path.exists():
            lines.append(f"- {label}: `{path}`")
    return "\n".join(lines)


# ── helpers ────────────────────────────────────────────────────────


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _fmt_int(v: Any) -> str:
    if isinstance(v, int):
        return f"{v:,}"
    if v is None:
        return "—"
    return str(v)


def _fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _render_reach_evidence(session_dir: Path) -> str:
    from ..core.tools.reach.evidence import list_reach_evidence

    records = list_reach_evidence(str(session_dir))
    if not records:
        return ""

    lines = ["## Reach Evidence", ""]
    lines.append(f"_{len(records)} evidence record(s) collected during the session._")
    lines.append("")

    # Group records by hypothesis_id (default to 'General' if None)
    grouped: dict[str, list[dict]] = {}
    for r in records:
        hypo = r.get("hypothesis_id") or "General"
        grouped.setdefault(hypo, []).append(r)

    # Sort groups so 'General' is last, others sorted alphabetically
    group_keys = sorted([k for k in grouped if k != "General"])
    if "General" in grouped:
        group_keys.append("General")

    for key in group_keys:
        lines.append(f"### Hypothesis: {key}")
        lines.append("")
        for r in grouped[key]:
            timestamp = r.get("timestamp", "")
            if timestamp and "T" in timestamp:
                time_part = timestamp.split("T")[1].rstrip("Z")[:8]
                ts_label = f"[{time_part}]"
            else:
                ts_label = ""

            tool = r.get("tool", "")
            source = r.get("source", "")
            title = r.get("title")
            title_part = f" - **{title}**" if title else ""
            
            lines.append(f"- {ts_label} `{tool}`: [{source}]({source}){title_part}")
            
            content = r.get("content", "").strip()
            if content:
                excerpt = content[:200].replace("\n", " ").strip()
                if len(content) > 200:
                    excerpt += "..."
                lines.append(f"  > {excerpt}")
            lines.append("")

    return "\n".join(lines).strip()


def _render_learned_memory(session_dir: Path, project_root: Path) -> str:
    try:
        from ..core.learning.memory import extract_memories_from_session
        from ..core.learning.skill_miner import mine_skills_from_memories
        from ..core.learning.store import LearningStore

        store = LearningStore(project_root)
        memories = extract_memories_from_session(session_dir, project_root)
        existing_skills = store.list_skills()

        stored_memories = 0
        created_skills = 0
        if memories:
            store.ensure()
            stored_memories = store.append_memories(memories, dedupe=True)
            created_skills = store.append_skills(
                mine_skills_from_memories(memories),
                dedupe=True,
            )

        lessons = [
            str(m.get("content") or m.get("title") or "").strip()
            for m in memories
            if m.get("kind") in {"lesson", "strategy", "decision"}
        ]
        if not lessons:
            lessons = [
                str(m.get("content") or m.get("title") or "").strip()
                for m in store.list_memories(limit=5)
                if m.get("kind") in {"lesson", "strategy", "decision"}
            ]

        skills_count = created_skills or min(len(existing_skills), 3)
        if not memories and not lessons and not skills_count:
            return ""

        lines = ["## Learned Memory", ""]
        lines.append(f"- Memories extracted: {len(memories)}")
        lines.append(f"- Skills used or created: {skills_count}")
        if stored_memories:
            lines.append(f"- New memories stored: {stored_memories}")
        if lessons:
            lines.append("- Key reusable lessons:")
            for lesson in lessons[:5]:
                excerpt = lesson[:180].replace("\n", " ").strip()
                if len(lesson) > 180:
                    excerpt += "..."
                lines.append(f"  - {excerpt}")
        return "\n".join(lines)
    except Exception:
        return ""


def _infer_learning_project_root(session_dir: Path) -> Path:
    from ..core.learning.store import infer_project_root_from_session

    return infer_project_root_from_session(session_dir)

