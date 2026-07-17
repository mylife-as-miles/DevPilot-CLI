from __future__ import annotations

from devpilot.cli.preflight import PreflightChecker
from devpilot.coordinator.config import CoordinatorConfig
from devpilot.coordinator.prompts import build_coordinator_system_prompt


def test_orbit_config_accepts_local_block():
    cfg = CoordinatorConfig(
        cwd=".",
        orbit={
            "enabled": True,
            "mode": "local",
            "database_path": "~/.orbit/custom.duckdb",
            "required": True,
        },
    )

    assert cfg.orbit.enabled is True
    assert cfg.orbit.mode == "local"
    assert cfg.orbit.database_path == "~/.orbit/custom.duckdb"
    assert cfg.orbit.required is True


def test_orbit_prompt_is_injected_when_enabled():
    cfg = CoordinatorConfig(
        cwd="/repo",
        orbit={"enabled": True, "mode": "local", "command": "orbit"},
    )

    prompt = build_coordinator_system_prompt(cfg)

    assert "GitLab Orbit Knowledge Graph" in prompt
    assert "Treat it as an\nimportant discovery process" in prompt
    assert "`orbit`" in prompt


def test_orbit_preflight_warns_when_optional_and_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("devpilot.cli.preflight.shutil.which", lambda _cmd: None)
    checker = PreflightChecker(
        tmp_path,
        provider="anthropic",
        explicit_api_key="test",
        orbit={"enabled": True, "required": False},
    )

    result = checker._check_orbit()

    assert result.status == "warn"
    assert result.name == "orbit"


def test_orbit_preflight_fails_when_required_and_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("devpilot.cli.preflight.shutil.which", lambda _cmd: None)
    checker = PreflightChecker(
        tmp_path,
        provider="anthropic",
        explicit_api_key="test",
        orbit={"enabled": True, "required": True},
    )

    result = checker._check_orbit()

    assert result.status == "fail"
    assert result.name == "orbit"
