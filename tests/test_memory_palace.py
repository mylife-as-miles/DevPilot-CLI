from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from devpilot.cli.app import app
from devpilot.cli.commands.memory_cmd import memory_app
from devpilot.core.memory_palace import bridge
from devpilot.core.memory_palace.context import build_long_term_memory_section
from devpilot.core.memory_palace.runner import config_path, palace_path
from devpilot.core.memory_palace.types import RunResult


runner = CliRunner()


def test_memory_help() -> None:
    result = runner.invoke(app, ["memory", "--help"])
    assert result.exit_code == 0
    assert "MemPalace" in result.output


def test_memory_doctor(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("devpilot.core.memory_palace.doctor.build_mempalace_invocation", lambda *a, **k: None)
    result = runner.invoke(memory_app, ["doctor"])
    assert result.exit_code == 0
    assert "DevPilot Memory doctor" in result.output
    assert (tmp_path / ".devpilot" / "memory").is_dir()


def test_vendored_path_detection(tmp_path: Path) -> None:
    vendor = tmp_path / "vendor" / "mempalace"
    (vendor / "mempalace").mkdir(parents=True)
    (vendor / "pyproject.toml").write_text('name = "mempalace"\n', encoding="utf-8")
    assert bridge.find_vendored_mempalace(tmp_path) == vendor


def test_missing_mempalace_gives_helpful_message(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(bridge.shutil, "which", lambda name: None)
    result = bridge.run_mempalace(["search", "query"], cwd=tmp_path)
    assert result.returncode == 127
    assert "install --dry-run" in result.stderr


def test_install_dry_run_prints_isolated_install_commands() -> None:
    result = runner.invoke(memory_app, ["install", "--dry-run"])
    assert result.exit_code == 0
    assert "uv tool install mempalace" in result.output
    assert "pipx install mempalace" in result.output
    assert ".venv-mempalace" in result.output


def test_memory_init_builds_mempalace_command(tmp_path: Path, monkeypatch) -> None:
    captured: list[list[str]] = []

    def fake_run(args, cwd=None, timeout=300, extra_env=None):
        captured.append(args)
        return _result(args, cwd)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("devpilot.core.memory_palace.runner.run_mempalace", fake_run)
    result = runner.invoke(memory_app, ["init"])

    assert result.exit_code == 0
    assert captured
    assert captured[0][0] == "--palace"
    assert captured[0][2:] == ["init", ".", "--yes", "--no-llm"]
    assert config_path(tmp_path).exists()


def test_memory_mine_builds_mempalace_command(tmp_path: Path, monkeypatch) -> None:
    captured: list[list[str]] = []

    def fake_run(args, cwd=None, timeout=300, extra_env=None):
        captured.append(args)
        return _result(args, cwd)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("devpilot.core.memory_palace.runner.run_mempalace", fake_run)
    result = runner.invoke(memory_app, ["mine", "--path", "."])

    assert result.exit_code == 0
    assert captured[0][2:] == ["mine", "."]


def test_sync_evidence_exports_fake_jsonl_to_markdown(tmp_path: Path, monkeypatch) -> None:
    session = tmp_path / ".devpilot" / "sessions" / "s1"
    session.mkdir(parents=True)
    (session / "reach_evidence.jsonl").write_text(
        json.dumps({
            "tool": "reach_search",
            "source": "web",
            "title": "Evaluator note",
            "content": "Validation requires a held-out split.",
            "hypothesis_id": "n1",
            "timestamp": "2026-07-04T00:00:00Z",
        }) + "\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("devpilot.core.memory_palace.runner.run_mempalace", lambda args, cwd=None, timeout=300, extra_env=None: _result(args, cwd))
    result = runner.invoke(memory_app, ["sync-evidence"])

    export = tmp_path / ".devpilot" / "memory" / "exports" / "reach_evidence.md"
    assert result.exit_code == 0
    assert export.exists()
    text = export.read_text(encoding="utf-8")
    assert "Evaluator note" in text
    assert "held-out split" in text


def test_sync_sessions_handles_missing_sessions_gracefully(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(memory_app, ["sync-sessions"])
    assert result.exit_code == 0
    assert "No .devpilot/sessions directory found" in result.output


def test_memory_search_builds_mempalace_command(tmp_path: Path, monkeypatch) -> None:
    captured: list[list[str]] = []

    def fake_run(args, cwd=None, timeout=120, extra_env=None):
        captured.append(args)
        return _result(args, cwd, stdout="result")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("devpilot.core.memory_palace.runner.run_mempalace", fake_run)
    result = runner.invoke(memory_app, ["search", "why evaluator", "--limit", "7", "--wing", "proj"])

    assert result.exit_code == 0
    assert captured[0][2:] == ["search", "why evaluator", "--results", "7", "--wing", "proj"]


def test_memory_wake_up_truncates_long_output(tmp_path: Path, monkeypatch) -> None:
    long_text = "x" * 1000

    def fake_run(args, cwd=None, timeout=120, extra_env=None):
        return _result(args, cwd, stdout=long_text)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("devpilot.core.memory_palace.runner.run_mempalace", fake_run)
    result = runner.invoke(memory_app, ["wake-up", "--max-chars", "220"])

    assert result.exit_code == 0
    assert "[truncated]" in result.output
    assert len(result.output) < 260


def test_bridge_uses_shell_false(tmp_path: Path, monkeypatch) -> None:
    vendor = tmp_path / "vendor" / "mempalace"
    (vendor / "mempalace").mkdir(parents=True)
    (vendor / "pyproject.toml").write_text('name = "mempalace"\n', encoding="utf-8")

    def fake_run(argv, **kwargs):
        assert kwargs["shell"] is False
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    result = bridge.run_mempalace(["--help"], cwd=tmp_path)
    assert result.ok


def test_no_global_storage_is_required(tmp_path: Path) -> None:
    local = palace_path(tmp_path)
    assert local == tmp_path.resolve() / ".devpilot" / "memory" / "mempalace-palace"
    local.relative_to(tmp_path.resolve())


def test_prompt_context_truncates_to_five_snippets(tmp_path: Path, monkeypatch) -> None:
    config_path(tmp_path).parent.mkdir(parents=True)
    config_path(tmp_path).write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr("devpilot.core.memory_palace.context.is_mempalace_available", lambda root: True)
    monkeypatch.setattr(
        "devpilot.core.memory_palace.context.wake_up",
        lambda **kwargs: _result(["wake-up"], tmp_path, stdout="\n".join(f"memory line {i}" for i in range(10))),
    )

    section = build_long_term_memory_section(tmp_path, query="goal", max_chars=4000, max_snippets=5)
    assert "## Long-Term Memory Context" in section
    assert section.count("- ") == 5
    assert "memory line 5" not in section


def _result(args, cwd, stdout: str = "ok") -> RunResult:
    return RunResult(
        argv=list(args),
        returncode=0,
        stdout=stdout,
        stderr="",
        cwd=str(cwd or Path(".")),
        source="test",
    )
