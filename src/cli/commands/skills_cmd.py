"""`devpilot skills` - read-only bundled and project skill browser."""

from __future__ import annotations

from pathlib import Path

import typer

from ...core.skill_registry import Skill, SkillRegistry, build_default_registry


skills_app = typer.Typer(
    name="skills",
    help="List and inspect DevPilot prompt skills.",
    no_args_is_help=True,
)


@skills_app.command("list")
def list_command() -> None:
    """List available built-in and project skills."""

    registry = build_default_registry(str(Path(".").resolve()))
    skills = _iter_skills(registry)
    if not skills:
        typer.echo("No DevPilot skills found.")
        return

    typer.echo(f"Available DevPilot skill(s): {len(skills)}\n")
    for skill in skills:
        typer.echo(f"{skill.name}  [{skill.source}]")
        typer.echo(f"  {skill.description}")
        if skill.when_to_apply:
            typer.echo(f"  When: {skill.when_to_apply}")
        typer.echo("")


@skills_app.command("show")
def show_command(
    skill_name: str = typer.Argument(..., help="Skill name to print, e.g. karpathy-coding."),
) -> None:
    """Print the full skill body."""

    registry = build_default_registry(str(Path(".").resolve()))
    skill = registry.get(skill_name)
    if skill is None:
        available = ", ".join(registry.names()) or "(none)"
        typer.secho(f"Skill not found: {skill_name}", fg=typer.colors.RED, err=True)
        typer.echo(f"Available: {available}", err=True)
        raise typer.Exit(code=2)

    if skill.when_to_apply:
        typer.echo(f"# Skill: {skill.name}")
        typer.echo(f"_When to apply: {skill.when_to_apply}_")
        typer.echo("")
    typer.echo(skill.body.rstrip())


def _iter_skills(registry: SkillRegistry) -> list[Skill]:
    skills: list[Skill] = []
    for name in registry.names():
        skill = registry.get(name)
        if skill is not None:
            skills.append(skill)
    return skills
