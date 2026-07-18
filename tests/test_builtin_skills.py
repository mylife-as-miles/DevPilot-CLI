from __future__ import annotations

import asyncio
from pathlib import Path

from typer.testing import CliRunner

from devpilot.cli.app import app
from devpilot.core.config import AgentConfig
from devpilot.core.skill_registry import build_default_registry
from devpilot.core.tools import get_all_tools
from devpilot.coordinator.config import CoordinatorConfig
from devpilot.coordinator.prompts import build_coordinator_system_prompt
from devpilot.executor.prompts import build_system_prompt


runner = CliRunner()
ROOT = Path(__file__).resolve().parent.parent


def test_karpathy_skill_file_exists() -> None:
    path = ROOT / "src" / "skills" / "karpathy_coding_guidelines.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "name: karpathy-coding" in text
    assert "# Karpathy Coding Guidelines for DevPilot" in text


def test_skill_packaging_metadata_includes_markdown_skills() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"devpilot.skills"' in pyproject
    assert '"*.md"' in pyproject


def test_skills_list_includes_karpathy_coding() -> None:
    result = runner.invoke(app, ["skills", "list"])
    assert result.exit_code == 0
    assert "karpathy-coding" in result.output
    assert "Careful, simple, surgical" in result.output


def test_skills_show_prints_karpathy_skill() -> None:
    result = runner.invoke(app, ["skills", "show", "karpathy-coding"])
    assert result.exit_code == 0
    assert "# Skill: karpathy-coding" in result.output
    assert "Karpathy Coding Guidelines for DevPilot" in result.output
    assert "Think Before Coding" in result.output
    assert "Goal-Driven Execution" in result.output


def test_skill_loader_can_access_karpathy_skill(tmp_path: Path) -> None:
    registry = build_default_registry(str(tmp_path))
    skill = registry.get("karpathy-coding")
    assert skill is not None
    assert "Surgical Changes" in skill.body


def test_executor_tools_include_load_skill_with_karpathy(tmp_path: Path) -> None:
    tools = get_all_tools(str(tmp_path), config=AgentConfig(cwd=str(tmp_path)))
    load_skill = next(tool for tool in tools if tool.name == "LoadSkill")
    assert "karpathy-coding" in load_skill.input_schema["properties"]["skill_name"]["enum"]

    body = asyncio.run(load_skill.execute(skill_name="karpathy-coding"))
    assert "Karpathy Coding Guidelines for DevPilot" in body


def test_executor_prompt_mentions_compact_skill_loading(tmp_path: Path) -> None:
    prompt = build_system_prompt(AgentConfig(cwd=str(tmp_path)))
    assert "Built-in coding discipline skill" in prompt
    assert 'LoadSkill(skill_name="karpathy-coding")' in prompt
    assert len(prompt) < 20000


def test_coordinator_prompt_can_reference_karpathy_skill(tmp_path: Path) -> None:
    prompt = build_coordinator_system_prompt(CoordinatorConfig(cwd=str(tmp_path)))
    assert "karpathy-coding" in prompt
    assert "additional_context" in prompt
