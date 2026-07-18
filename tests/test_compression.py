from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from devpilot.cli.app import app
from devpilot.cli.commands.compress_cmd import compress_app
from devpilot.core.compression import bridge
from devpilot.core.compression.evidence_compressor import compress_evidence
from devpilot.core.compression.prompt_context import maybe_compress_prompt_context
from devpilot.core.compression.runner import compression_dir, compress_text_file
from devpilot.core.compression.session_compressor import compress_logs, compress_session
from devpilot.core.compression.types import RunResult


runner = CliRunner()


def test_compress_help() -> None:
    result = runner.invoke(app, ["compress", "--help"])
    assert result.exit_code == 0
    assert "Headroom" in result.output


def test_compress_doctor(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("devpilot.core.compression.doctor.build_headroom_invocation", lambda *a, **k: None)
    result = runner.invoke(compress_app, ["doctor"])
    assert result.exit_code == 0
    assert "DevPilot Compression doctor" in result.output
    assert (tmp_path / ".devpilot" / "compression").is_dir()


def test_vendored_headroom_detection(tmp_path: Path) -> None:
    vendor = tmp_path / "vendor" / "headroom"
    (vendor / "headroom").mkdir(parents=True)
    (vendor / "pyproject.toml").write_text('name = "headroom-ai"\n', encoding="utf-8")
    assert bridge.find_vendored_headroom(tmp_path) == vendor


def test_missing_headroom_gives_helpful_message(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(bridge, "find_vendored_headroom", lambda root: None)
    monkeypatch.setattr(bridge.shutil, "which", lambda name: None)
    result = bridge.run_headroom(["doctor"], cwd=tmp_path)
    assert result.returncode == 127
    assert "compress install --dry-run" in result.stderr


def test_install_dry_run_prints_safe_commands() -> None:
    result = runner.invoke(compress_app, ["install", "--dry-run"])
    assert result.exit_code == 0
    assert 'pip install "headroom-ai[all]"' in result.output
    assert 'pip install "headroom-ai[proxy]"' in result.output
    assert "uvx --from" in result.output


def test_text_compression_builds_headroom_command(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "README.md"
    source.write_text("hello\n" * 100, encoding="utf-8")
    captured: list[list[str]] = []

    def fake_python(script, args, cwd=None, timeout=300, extra_env=None):
        captured.append(args)
        return _result(args, cwd, stdout="compressed")

    monkeypatch.setattr("devpilot.core.compression.runner.run_headroom_python", fake_python)
    result = compress_text_file(source, project_root=tmp_path, max_chars=123)

    assert result.ok
    assert result.stdout == "compressed"
    assert captured == [[str(source), "123"]]


def test_session_compression_handles_missing_session_gracefully(tmp_path: Path) -> None:
    artifact = compress_session(tmp_path)
    assert artifact.path is None
    assert "No sessions found" in artifact.message


def test_evidence_compression_preserves_source_urls(tmp_path: Path) -> None:
    session = tmp_path / ".devpilot" / "sessions" / "s1"
    session.mkdir(parents=True)
    (session / "reach_evidence.jsonl").write_text(
        json.dumps({
            "title": "Paper",
            "source": "https://example.com/paper",
            "hypothesis_id": "n3",
            "content": "Important evidence about validation.",
        }) + "\n",
        encoding="utf-8",
    )
    artifact = compress_evidence(tmp_path, "s1")
    assert artifact.path is not None
    text = artifact.path.read_text(encoding="utf-8")
    assert "https://example.com/paper" in text
    assert "n3" in text


def test_logs_compression_preserves_failing_test_names(tmp_path: Path) -> None:
    session = tmp_path / ".devpilot" / "sessions" / "s2"
    session.mkdir(parents=True)
    (session / "executor.log").write_text(
        "lots\n" * 50 + "FAILED tests/test_eval.py::test_metric_regression\nAssertionError\n",
        encoding="utf-8",
    )
    artifact = compress_logs(tmp_path, "s2")
    assert artifact.path is not None
    text = artifact.path.read_text(encoding="utf-8")
    assert "test_metric_regression" in text


def test_prompt_compression_falls_back_if_headroom_missing(tmp_path: Path, monkeypatch) -> None:
    class Cfg:
        enabled = True
        compress_reach_evidence = True
        compress_memory_context = True
        max_context_chars = 20

    text = "x" * 200
    monkeypatch.setattr("devpilot.core.compression.prompt_context.is_headroom_available", lambda root: False)
    assert maybe_compress_prompt_context(text, project_root=tmp_path, compression_config=Cfg(), kind="reach") == text


def test_bridge_uses_shell_false(tmp_path: Path, monkeypatch) -> None:
    vendor = tmp_path / "vendor" / "headroom"
    (vendor / "headroom").mkdir(parents=True)
    (vendor / "pyproject.toml").write_text('name = "headroom-ai"\n', encoding="utf-8")

    def fake_run(argv, **kwargs):
        assert kwargs["shell"] is False
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)
    result = bridge.run_headroom(["--help"], cwd=tmp_path)
    assert result.ok


def test_no_global_storage_required(tmp_path: Path) -> None:
    local = compression_dir(tmp_path)
    assert local == tmp_path.resolve() / ".devpilot" / "compression"
    local.relative_to(tmp_path.resolve())


def _result(args, cwd, stdout: str = "ok") -> RunResult:
    return RunResult(
        argv=list(args),
        returncode=0,
        stdout=stdout,
        stderr="",
        cwd=str(cwd or Path(".")),
        source="test",
    )
