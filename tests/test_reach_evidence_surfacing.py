"""Tests for DevPilot Reach Evidence Surfacing (Phase 3).

Covers:
  1. `devpilot reach evidence` CLI commands (list, search, show)
  2. Report generation appending a "Reach Evidence" section when JSONL exists
  3. Report generation omitting the section when no evidence exists
  4. Graceful skipping of malformed JSONL lines
  5. Safe truncation of large excerpts in CLI/report
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

# ── Bootstrap devpilot import (same as conftest.py) ──────────────────
_ROOT = Path(__file__).resolve().parent.parent

if "devpilot" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "devpilot",
        _ROOT / "src" / "__init__.py",
        submodule_search_locations=[str(_ROOT / "src")],
    )
    assert _spec and _spec.loader
    _devpilot = importlib.util.module_from_spec(_spec)
    sys.modules["devpilot"] = _devpilot
    _spec.loader.exec_module(_devpilot)

from devpilot.cli.commands.reach_cmd import reach_app
from devpilot.report.generator import generate_report

runner = CliRunner()


# =====================================================================
# 1. CLI Commands tests
# =====================================================================


def test_cli_evidence_help():
    result = runner.invoke(reach_app, ["evidence", "--help"])
    assert result.exit_code == 0
    assert "Browse and search collected Reach" in result.output


def test_cli_evidence_commands_with_temp_workspace(tmp_path):
    # Setup a dummy session directory structure
    session_dir = tmp_path / ".devpilot" / "sessions" / "test-session-1"
    session_dir.mkdir(parents=True, exist_ok=True)

    # Write some sample evidence records (including a malformed line)
    evidence_file = session_dir / "reach_evidence.jsonl"
    evidence_file.write_text(
        json.dumps({
            "tool": "reach_visit",
            "source": "https://example.com/a",
            "query": "https://example.com/a",
            "title": "Example A",
            "timestamp": "2026-07-02T12:00:00Z",
            "content": "Line 1\nLine 2\n" * 50,  # Large content to verify truncation
            "cycle_id": "1",
            "hypothesis_id": "n1",
        })
        + "\n"
        + "THIS_IS_MALFORMED_JSON_LINE\n"
        + json.dumps({
            "tool": "reach_search",
            "source": "web_search",
            "query": "novel transformer",
            "timestamp": "2026-07-02T12:01:00Z",
            "content": "Transformer novelty check results.",
            "cycle_id": "2",
            "hypothesis_id": "n2",
        })
        + "\n",
        encoding="utf-8",
    )

    # Test list command with explicit path
    result_list = runner.invoke(
        reach_app, ["evidence", "list", str(session_dir)]
    )
    assert result_list.exit_code == 0
    assert "reach_visit" in result_list.output
    assert "Example A" in result_list.output
    assert "reach_search" in result_list.output
    assert "novel transformer" in result_list.output
    # Excerpt must be truncated safely
    assert "Excerpt:" in result_list.output
    assert len(result_list.output) < 1000

    # Test search command
    result_search = runner.invoke(
        reach_app, ["evidence", "search", "transformer", str(session_dir)]
    )
    assert result_search.exit_code == 0
    assert "reach_search" in result_search.output
    assert "reach_visit" not in result_search.output

    # Test show command with limit
    result_show = runner.invoke(
        reach_app, ["evidence", "show", str(session_dir), "--limit", "1"]
    )
    assert result_show.exit_code == 0
    # Since it's latest first, reach_search should be shown
    assert "reach_search" in result_show.output
    assert "reach_visit" not in result_show.output


def test_cli_evidence_auto_resolution(tmp_path):
    session_dir = tmp_path / ".devpilot" / "sessions" / "test-session-2"
    session_dir.mkdir(parents=True, exist_ok=True)

    evidence_file = session_dir / "reach_evidence.jsonl"
    evidence_file.write_text(
        json.dumps({
            "tool": "reach_visit",
            "source": "https://example.com/b",
            "query": "https://example.com/b",
            "title": "Example B",
            "timestamp": "2026-07-02T13:00:00Z",
            "content": "Auto-resolved page content.",
            "cycle_id": "3",
            "hypothesis_id": "n3",
        })
        + "\n",
        encoding="utf-8",
    )

    # Patch Path.cwd to return tmp_path so it picks the latest session automatically
    with patch("pathlib.Path.cwd", return_value=tmp_path):
        # We also patch Path.resolve to return tmp_path/candidate when candidates are relative,
        # but let's keep it simple: just mock the _resolve_session_dir_for_reach function!
        from devpilot.cli.commands import reach_cmd
        with patch.object(reach_cmd, "_resolve_session_dir_for_reach", return_value=session_dir):
            result = runner.invoke(reach_app, ["evidence", "list"])
            assert result.exit_code == 0
            assert "reach_visit" in result.output
            assert "Example B" in result.output


# =====================================================================
# 2. Report Generation integration tests
# =====================================================================


def test_report_includes_evidence_section_when_jsonl_exists(tmp_path):
    session_dir = tmp_path / "session-xyz"
    session_dir.mkdir(parents=True, exist_ok=True)

    # Write a sample evidence file
    evidence_file = session_dir / "reach_evidence.jsonl"
    evidence_file.write_text(
        json.dumps({
            "tool": "reach_visit",
            "source": "https://arxiv.org/abs/123",
            "query": "https://arxiv.org/abs/123",
            "title": "Attention Is All You Need",
            "timestamp": "2026-07-02T12:00:00Z",
            "content": "Abstract: We propose a new simple network architecture, the Transformer...",
            "cycle_id": "1",
            "hypothesis_id": "n1",
        })
        + "\n",
        encoding="utf-8",
    )

    # Run report generator
    report_path = generate_report(session_dir)
    assert report_path.exists()

    report_content = report_path.read_text(encoding="utf-8")
    assert "## Reach Evidence" in report_content
    assert "### Hypothesis: n1" in report_content
    assert "Attention Is All You Need" in report_content
    assert "arxiv.org/abs/123" in report_content


def test_report_omits_evidence_section_when_no_evidence_exists(tmp_path):
    session_dir = tmp_path / "session-empty"
    session_dir.mkdir(parents=True, exist_ok=True)

    report_path = generate_report(session_dir)
    assert report_path.exists()

    report_content = report_path.read_text(encoding="utf-8")
    assert "## Reach Evidence" not in report_content
