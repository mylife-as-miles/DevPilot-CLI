"""`devpilot learn` - local learning memory and skill commands."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import typer

from ..._app import CONFIG_DIR_NAME
from ...core.learning.memory import extract_memories_from_session
from ...core.learning.search import search_memories
from ...core.learning.skill_miner import mine_skills_from_memories
from ...core.learning.store import LearningStore, infer_project_root_from_session
from ...core.learning.trajectory import compress_session_trajectory


learn_app = typer.Typer(
    name="learn",
    help="Local DevPilot learning memory, skills, and trajectory tools.",
    no_args_is_help=True,
)

memory_app = typer.Typer(
    name="memory",
    help="List and search learned local memories.",
    no_args_is_help=True,
)
skills_app = typer.Typer(
    name="skills",
    help="Mine, list, and inspect learned skills.",
    no_args_is_help=True,
)
trajectory_app = typer.Typer(
    name="trajectory",
    help="Compress session trajectories.",
    no_args_is_help=True,
)

learn_app.add_typer(memory_app, name="memory")
learn_app.add_typer(skills_app, name="skills")
learn_app.add_typer(trajectory_app, name="trajectory")


@learn_app.command("doctor")
def doctor_command() -> None:
    """Check the local learning store and imports."""
    cwd = Path(".").resolve()
    store = LearningStore(cwd)
    problems: list[str] = []

    try:
        store.ensure()
        typer.echo(f"OK .devpilot store: {store.devpilot_dir}")
    except OSError as exc:
        problems.append(f"Could not create {store.devpilot_dir}: {exc}")

    if store.is_project_local():
        typer.echo(f"OK local memory path: {store.memory_dir}")
    else:
        problems.append(f"Memory path is not project-local: {store.memory_dir}")

    if store.check_writable():
        typer.echo("OK memory, skill, and trajectory stores are writable")
    else:
        problems.append("Learning store is not writable")

    for module in (
        "devpilot.core.learning.types",
        "devpilot.core.learning.store",
        "devpilot.core.learning.memory",
        "devpilot.core.learning.skill_miner",
        "devpilot.core.learning.trajectory",
        "devpilot.core.learning.search",
    ):
        try:
            importlib.import_module(module)
        except Exception as exc:
            problems.append(f"Import failed for {module}: {exc}")

    if problems:
        for problem in problems:
            typer.secho(f"FAIL {problem}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho("OK package imports work", fg=typer.colors.GREEN)
    typer.echo("OK global learning storage is not used")


@learn_app.command("summarize")
def summarize_command(
    session: str = typer.Argument(None, help="Session name or directory path. Defaults to latest session."),
) -> None:
    """Extract and print a compact learning summary for a session."""
    session_dir = _resolve_session_dir(session)
    if session_dir is None:
        typer.echo("No sessions found in .devpilot/sessions/.")
        return
    project_root = infer_project_root_from_session(session_dir)
    memories = extract_memories_from_session(session_dir, project_root)
    evidence = _read_evidence_count(session_dir)
    trajectory = compress_session_trajectory(session_dir)

    typer.echo(f"Session: {session_dir.name}")
    typer.echo(f"Evidence records: {evidence}")
    typer.echo(f"Extracted memories: {len(memories)}")
    typer.echo("")
    typer.echo(trajectory["summary"])


@memory_app.command("list")
def memory_list_command(
    limit: int = typer.Option(20, "--limit", min=1, help="Maximum records to list."),
    kind: str = typer.Option(None, "--kind", help="Filter by memory kind."),
    tag: str = typer.Option(None, "--tag", help="Filter by tag."),
) -> None:
    """List stored memories."""
    records = LearningStore(Path(".").resolve()).list_memories(limit=limit, kind=kind, tag=tag)
    if not records:
        typer.echo("No learned memories found.")
        return
    typer.echo(f"Showing {len(records)} learned memory record(s):\n")
    for record in records:
        _print_memory(record)


@memory_app.command("search")
def memory_search_command(
    query: str = typer.Argument(..., help="Case-insensitive memory query."),
    limit: int = typer.Option(20, "--limit", min=1, help="Maximum records to list."),
) -> None:
    """Search learned memories."""
    records = search_memories(Path(".").resolve(), query, limit=limit)
    if not records:
        typer.echo(f"No memories matching {query!r}.")
        return
    typer.echo(f"Found {len(records)} matching memory record(s):\n")
    for record in records:
        _print_memory(record)


@skills_app.command("mine")
def skills_mine_command(
    session: str = typer.Argument(None, help="Session name or directory path. Defaults to latest session."),
) -> None:
    """Extract memories from a session and store any new skill candidates."""
    session_dir = _resolve_session_dir(session)
    if session_dir is None:
        typer.echo("No sessions found in .devpilot/sessions/.")
        return
    project_root = infer_project_root_from_session(session_dir)
    store = LearningStore(project_root)
    store.ensure()

    memories = extract_memories_from_session(session_dir, project_root)
    stored_memories = store.append_memories(memories, dedupe=True)
    skills = mine_skills_from_memories(memories)
    stored_skills = store.append_skills(skills, dedupe=True)

    typer.echo(f"Session: {session_dir.name}")
    typer.echo(f"Memories extracted: {len(memories)}")
    typer.echo(f"Memories stored: {stored_memories}")
    typer.echo(f"Skills created: {stored_skills}")
    typer.echo(f"Duplicate skills skipped: {max(0, len(skills) - stored_skills)}")


@skills_app.command("list")
def skills_list_command(
    limit: int = typer.Option(20, "--limit", min=1, help="Maximum skills to list."),
) -> None:
    """List generated skills."""
    skills = LearningStore(Path(".").resolve()).list_skills(limit=limit)
    if not skills:
        typer.echo("No learned skills found.")
        return
    typer.echo(f"Showing {len(skills)} learned skill(s):\n")
    for skill in skills:
        _print_skill(skill)


@skills_app.command("show")
def skills_show_command(
    skill_id: str = typer.Argument(..., help="Skill id or skill name."),
) -> None:
    """Print the full stored skill record."""
    store = LearningStore(Path(".").resolve())
    skill = store.get_skill(skill_id)
    if skill is None:
        skill = next((s for s in store.list_skills() if s.get("name") == skill_id), None)
    if skill is None:
        typer.secho(f"Skill not found: {skill_id}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    typer.echo(json.dumps(skill, indent=2, ensure_ascii=False))


@trajectory_app.command("compress")
def trajectory_compress_command(
    session: str = typer.Argument(None, help="Session name or directory path. Defaults to latest session."),
) -> None:
    """Create a compact trajectory record for a session."""
    session_dir = _resolve_session_dir(session)
    if session_dir is None:
        typer.echo("No sessions found in .devpilot/sessions/.")
        return
    project_root = infer_project_root_from_session(session_dir)
    store = LearningStore(project_root)
    store.ensure()
    trajectory = compress_session_trajectory(session_dir)
    stored = store.append_trajectory(trajectory, dedupe=True)

    typer.echo(f"Session: {session_dir.name}")
    typer.echo(f"Trajectory: {trajectory['id']}")
    typer.echo("Stored: yes" if stored else "Stored: duplicate skipped")
    typer.echo("")
    typer.echo(trajectory["summary"])


def _resolve_session_dir(session: str | None) -> Path | None:
    cwd = Path(".").resolve()
    if session:
        candidate = Path(session)
        if candidate.is_absolute() and candidate.exists():
            return candidate.resolve()
        if candidate.exists():
            return candidate.resolve()
        by_name = cwd / CONFIG_DIR_NAME / "sessions" / session
        if by_name.exists():
            return by_name.resolve()
        typer.secho(f"Session not found: {session}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    sessions_root = cwd / CONFIG_DIR_NAME / "sessions"
    if not sessions_root.is_dir():
        return None
    sessions = [p for p in sessions_root.iterdir() if p.is_dir() and not p.name.startswith(".")]
    if not sessions:
        return None
    sessions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return sessions[0].resolve()


def _read_evidence_count(session_dir: Path) -> int:
    from ...core.learning.session_reader import read_reach_evidence

    return len(read_reach_evidence(session_dir))


def _print_memory(record: Any) -> None:
    tags = ", ".join(str(t) for t in record.get("tags", []) or [])
    tag_part = f" [{tags}]" if tags else ""
    typer.echo(f"{record.get('id')}  {record.get('kind')}  {record.get('title')}{tag_part}")
    content = str(record.get("content") or "")
    if content:
        typer.echo(f"  {_compact(content, 180)}")
    typer.echo("")


def _print_skill(skill: Any) -> None:
    typer.echo(f"{skill.get('id')}  {skill.get('name')}")
    typer.echo(f"  Trigger: {skill.get('trigger') or ''}")
    typer.echo(f"  {skill.get('description') or ''}")
    typer.echo("")


def _compact(text: str, max_chars: int) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= max_chars:
        return clean
    return clean[: max_chars - 3].rstrip() + "..."
