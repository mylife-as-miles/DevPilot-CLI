"""Tests for the DevPilot iFixAi audit integration.

The external iFixAi execution path is mocked where needed so tests stay local
and do not require network access or provider credentials.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devpilot.cli.app import app
from devpilot.cli.commands.audit_cmd import audit_app
from devpilot.core.audit import ifixai_bridge
from devpilot.core.audit.devpilot_adapter import DevPilotAuditAdapter
from devpilot.core.audit.ifixai_bridge import IfixAiResult
from devpilot.core.audit.runner import (
    AuditRunConfig,
    AuditRunError,
    audit_output_dir,
    audit_reliability_dir,
    build_run_args,
    run_audit,
)


runner = CliRunner()


def _make_vendored_ifixai(root: Path) -> Path:
    vendored = root / "vendor" / "iFixAi"
    (vendored / "ifixai").mkdir(parents=True)
    (vendored / "pyproject.toml").write_text('[project]\nlicense = {text = "Apache-2.0"}\n', encoding="utf-8")
    (vendored / "LICENSE").write_text("Apache License\nVersion 2.0\n", encoding="utf-8")
    return vendored


def test_devpilot_audit_help() -> None:
    result = runner.invoke(app, ["audit", "--help"])
    assert result.exit_code == 0
    assert "Run local iFixAi audits" in result.output
    assert "doctor" in result.output


def test_audit_doctor_graceful(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_vendored_ifixai(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "devpilot.core.audit.doctor.run_ifixai",
        lambda *args, **kwargs: IfixAiResult([], 0, "help", "", str(tmp_path), "vendored"),
    )

    result = runner.invoke(audit_app, ["doctor"])

    assert result.exit_code == 0
    assert "DevPilot Audit doctor" in result.output
    assert "no global audit storage is used" in result.output


def test_audit_install_dry_run() -> None:
    result = runner.invoke(audit_app, ["install", "--dry-run"])
    assert result.exit_code == 0
    assert "No changes were made" in result.output
    assert "vendor/iFixAi" in result.output


def test_bridge_uses_shell_false_and_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _make_vendored_ifixai(tmp_path)
    calls: list[dict] = []

    def fake_run(argv, **kwargs):
        calls.append({"argv": argv, **kwargs})
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

    monkeypatch.setattr(ifixai_bridge.subprocess, "run", fake_run)

    result = ifixai_bridge.run_ifixai(["--help"], cwd=tmp_path, timeout=7)

    assert result.ok
    assert calls
    assert calls[0]["shell"] is False
    assert calls[0]["timeout"] == 7
    assert calls[0]["cwd"] == str(tmp_path)
    assert str(tmp_path / "vendor" / "iFixAi") in calls[0]["env"]["PYTHONPATH"]


def test_audit_run_mock_cli_uses_safe_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run_audit(config, *, project_root=None):
        assert config.provider == "mock"
        assert config.suite == "smoke"
        return type(
            "Outcome",
            (),
            {
                "result": IfixAiResult(["ifixai"], 0, "mock ok", "", str(tmp_path), "vendored"),
                "output_dir": tmp_path / ".devpilot" / "audit" / "ifixai-results",
                "display_args": ["run", "--provider", "mock", "--api-key", "<redacted>"],
            },
        )()

    monkeypatch.setattr("devpilot.cli.commands.audit_cmd.run_audit", fake_run_audit)

    result = runner.invoke(audit_app, ["run", "--provider", "mock", "--suite", "smoke"])

    assert result.exit_code == 0
    assert "mock ok" in result.output
    assert "<redacted>" in result.output


def test_external_provider_requires_api_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(AuditRunError):
        run_audit(AuditRunConfig(provider="openai"), project_root=tmp_path)


def test_api_key_is_redacted_from_results(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    secret = "sk-secret-value"
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    def fake_run_ifixai(args, **kwargs):
        return IfixAiResult(
            argv=args,
            returncode=0,
            stdout=f"stdout {secret}",
            stderr=f"stderr {secret}",
            cwd=str(tmp_path),
            source="vendored",
        )

    monkeypatch.setattr("devpilot.core.audit.runner.run_ifixai", fake_run_ifixai)

    outcome = run_audit(AuditRunConfig(provider="openai"), project_root=tmp_path)
    combined = " ".join(outcome.display_args + outcome.result.argv) + outcome.result.stdout + outcome.result.stderr

    assert secret not in combined
    assert "<redacted>" in combined


def test_audit_ifixai_help_falls_back_when_upstream_deps_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "devpilot.cli.commands.audit_cmd.run_ifixai",
        lambda *args, **kwargs: IfixAiResult([], 1, "", "ModuleNotFoundError: No module named 'json_repair'", ".", "vendored"),
    )

    result = runner.invoke(audit_app, ["ifixai", "--help"])

    assert result.exit_code == 0
    assert "DevPilot audit pass-through" in result.output
    assert "install --dry-run" in result.output


def test_audit_setup_preflights_missing_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "devpilot.cli.commands.audit_cmd.audit_doctor.missing_ifixai_core_packages",
        lambda: ["json_repair"],
    )

    result = runner.invoke(audit_app, ["setup", "--launch"])

    assert result.exit_code == 1
    assert "Setup was not launched" in result.output
    assert "json_repair" in result.output


def test_audit_setup_defaults_to_guidance() -> None:
    result = runner.invoke(audit_app, ["setup"])
    assert result.exit_code == 0
    assert "No setup was launched" in result.output
    assert "--launch" in result.output


def test_audit_report_summarizes_latest_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    reports_dir = tmp_path / ".devpilot" / "audit" / "ifixai-results"
    reports_dir.mkdir(parents=True)
    report = {
        "metadata": {"provider": "mock", "suite": "smoke"},
        "overall": {"grade": "B", "passed": False},
        "insights": {"total_tests": 2},
        "warnings": ["self-judge"],
        "test_results": [
            {"test_id": "B01", "name": "Tool governance", "status": "fail", "passing": False},
            {"test_id": "B02", "name": "Pass", "status": "pass", "passing": True},
        ],
    }
    (reports_dir / "ifixai-mock.json").write_text(json.dumps(report), encoding="utf-8")

    result = runner.invoke(audit_app, ["report"])

    assert result.exit_code == 0
    assert "Grade: B" in result.output
    assert "B01: Tool governance" in result.output


def test_audit_report_handles_missing_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(audit_app, ["report"])
    assert result.exit_code == 0
    assert "No iFixAi reports found" in result.output


def test_audit_storage_is_project_local(tmp_path: Path) -> None:
    output = audit_output_dir(tmp_path)
    assert output == tmp_path / ".devpilot" / "audit" / "ifixai-results"
    assert output.relative_to(tmp_path) == Path(".devpilot") / "audit" / "ifixai-results"
    reliability = audit_reliability_dir(tmp_path)
    assert reliability == tmp_path / ".devpilot" / "audit" / "ifixai-runs"


def test_run_args_keep_reliability_artifacts_under_devpilot(tmp_path: Path) -> None:
    output = tmp_path / ".devpilot" / "audit" / "ifixai-results"
    args = build_run_args(AuditRunConfig(output_dir=output), api_key="key")
    assert "--reliability-out" in args
    assert args[args.index("--reliability-out") + 1] == str(tmp_path / ".devpilot" / "audit" / "ifixai-runs")


def test_devpilot_adapter_phase_one_scaffold() -> None:
    adapter = DevPilotAuditAdapter(project_name="Demo")
    assert adapter.list_tools() == []
    assert adapter.get_audit_trail() == []
    with pytest.raises(NotImplementedError):
        adapter.send_message("hello")
