from pathlib import Path

import pytest

from devpilot.acp.runtime import (
    DEVPILOT_MODES,
    AcpSession,
    build_run_invocation,
    event_log_path,
    extract_prompt_text,
)


def test_modes_match_the_desktop_contract() -> None:
    assert [mode.id for mode in DEVPILOT_MODES] == [
        "research",
        "plan",
        "execute",
        "review",
        "audit",
        "memory",
    ]


def test_research_invocation_is_an_argument_array_without_shell_text(tmp_path: Path) -> None:
    session = AcpSession(
        session_id="session-1",
        cwd=tmp_path,
        mode="research",
        run_name="acp-session-1",
    )

    invocation = build_run_invocation(session, "Improve the parser")

    assert invocation[1:4] == ("-m", "devpilot.cli.app", "run")
    assert "--yes" in invocation
    yes_cwd_value_index = invocation.index("--yes-cwd") + 1
    assert invocation[yes_cwd_value_index] == str(tmp_path)
    assert "--no-dashboard-input" in invocation
    assert "--no-webui" in invocation
    assert "--no-followup" in invocation


def test_execute_mode_limits_the_run_to_one_cycle(tmp_path: Path) -> None:
    session = AcpSession(
        session_id="session-2",
        cwd=tmp_path,
        mode="execute",
        run_name="acp-session-2",
    )
    invocation = build_run_invocation(session, "Fix one bug")
    assert invocation[invocation.index("--max-cycles") + 1] == "1"


def test_resume_uses_the_existing_run_checkpoint(tmp_path: Path) -> None:
    session = AcpSession(
        session_id="session-3",
        cwd=tmp_path,
        mode="research",
        run_name="acp-session-3",
        has_started=True,
    )
    invocation = build_run_invocation(session, "Continue")
    assert "--resume" in invocation


def test_event_log_path_matches_the_cli_run_workspace(tmp_path: Path) -> None:
    session = AcpSession(session_id="session-4", cwd=tmp_path, run_name="acp-session-4")
    assert event_log_path(session) == tmp_path / ".devpilot" / "sessions" / "acp-session-4" / "events.jsonl"


def test_prompt_extraction_accepts_only_text_blocks() -> None:
    assert extract_prompt_text([
        {"type": "text", "text": "First"},
        {"type": "image", "data": "ignored"},
        {"type": "text", "text": "Second"},
    ]) == "First\n\nSecond"


def test_prompt_extraction_rejects_an_empty_prompt() -> None:
    with pytest.raises(ValueError, match="text"):
        extract_prompt_text([])
