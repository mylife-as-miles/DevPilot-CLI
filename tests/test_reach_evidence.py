"""Tests for the DevPilot Reach Evidence Store.

Covers:
  1. save_reach_evidence, list_reach_evidence, search_reach_evidence APIs
  2. Append-only JSONL files
  3. Reach runtime tools saving evidence when workspace_dir is present
  4. Reach tools running fine and NOT saving when workspace_dir is None
  5. Correct cycle/hypothesis IDs saved in records
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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


from devpilot.core.tools.reach.evidence import (
    list_reach_evidence,
    save_reach_evidence,
    search_reach_evidence,
)
from devpilot.core.tools.reach.runtime_tools import (
    ReachVisitTool,
    ReachSearchTool,
)
from devpilot.core.config import AgentConfig


# =====================================================================
# 1. API tests with temporary directories
# =====================================================================


def test_save_list_search_evidence(tmp_path):
    wdir = str(tmp_path)

    # 1. Save records
    path1 = save_reach_evidence(
        wdir,
        tool_name="reach_visit",
        source="https://example.com/one",
        query="https://example.com/one",
        content="This is the first test page content.",
        title="Example One",
        cycle_id="1",
        hypothesis_id="n1",
    )
    assert path1 == os.path.join(wdir, "reach_evidence.jsonl")
    assert os.path.exists(path1)

    path2 = save_reach_evidence(
        wdir,
        tool_name="reach_search",
        source="web_search",
        query="deep learning",
        content="Some search results about deep learning.",
        cycle_id="2",
        hypothesis_id="n2",
    )
    assert path2 == path1

    # 2. List records
    records = list_reach_evidence(wdir)
    assert len(records) == 2
    assert records[0]["tool"] == "reach_visit"
    assert records[0]["source"] == "https://example.com/one"
    assert records[0]["query"] == "https://example.com/one"
    assert records[0]["content"] == "This is the first test page content."
    assert records[0]["title"] == "Example One"
    assert records[0]["cycle_id"] == "1"
    assert records[0]["hypothesis_id"] == "n1"
    assert "timestamp" in records[0]

    assert records[1]["tool"] == "reach_search"
    assert records[1]["source"] == "web_search"
    assert records[1]["query"] == "deep learning"
    assert records[1]["content"] == "Some search results about deep learning."
    assert records[1]["title"] is None
    assert records[1]["cycle_id"] == "2"
    assert records[1]["hypothesis_id"] == "n2"

    # 3. Search records
    res1 = search_reach_evidence(wdir, "first")
    assert len(res1) == 1
    assert res1[0]["title"] == "Example One"

    res2 = search_reach_evidence(wdir, "deep learning")
    assert len(res2) == 1
    assert res2[0]["tool"] == "reach_search"

    res3 = search_reach_evidence(wdir, "n1")
    assert len(res3) == 1
    assert res3[0]["hypothesis_id"] == "n1"

    res4 = search_reach_evidence(wdir, "nonexistent")
    assert len(res4) == 0


def test_list_and_search_empty_or_missing(tmp_path):
    assert list_reach_evidence(None) == []
    assert search_reach_evidence(None, "test") == []
    assert list_reach_evidence(str(tmp_path / "nonexistent")) == []


# =====================================================================
# 2. Tool integration tests
# =====================================================================


class TestToolEvidenceIntegration:
    @patch("devpilot.core.tools.reach.channels.web.requests.get")
    def test_visit_saves_evidence_when_workspace_active(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = "Title: Page One\nURL: https://example.com/page1\n\nContent here."
        mock_get.return_value = mock_resp

        wdir = str(tmp_path)
        config = AgentConfig(node_id="n5", cycle_id="3")

        tool = ReachVisitTool(cwd=str(tmp_path), workspace_dir=wdir, config=config)
        result = asyncio.run(tool.execute(url="https://example.com/page1"))

        # Check evidence was saved
        records = list_reach_evidence(wdir)
        assert len(records) == 1
        r = records[0]
        assert r["tool"] == "reach_visit"
        assert r["source"] == "https://example.com/page1"
        assert r["query"] == "https://example.com/page1"
        assert r["title"] == "Page One"
        assert r["cycle_id"] == "3"
        assert r["hypothesis_id"] == "n5"

    @patch("devpilot.core.tools.reach.channels.web.requests.get")
    def test_visit_does_not_save_evidence_when_workspace_none(self, mock_get, tmp_path):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = "Title: Page One\nURL: https://example.com/page1\n\nContent here."
        mock_get.return_value = mock_resp

        tool = ReachVisitTool(cwd=str(tmp_path), workspace_dir=None)
        result = asyncio.run(tool.execute(url="https://example.com/page1"))

        # No evidence file should exist
        evidence_file = tmp_path / "reach_evidence.jsonl"
        assert not evidence_file.exists()
