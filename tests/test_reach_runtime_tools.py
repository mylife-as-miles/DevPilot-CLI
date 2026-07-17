"""Tests for DevPilot Reach runtime tools.

Covers:
  1. Tool schema validity (name, description, input_schema, is_read_only)
  2. Successful mocked execution for each tool
  3. Graceful missing-dependency responses
  4. Registry integration (tools appear in get_all_tools)
  5. No shell=True (inherits the AST audit from test_reach.py)
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import types
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


from devpilot.core.tools import get_all_tools
from devpilot.core.tools.reach.runtime_tools import (
    ReachGitHubRepoTool,
    ReachRSSReadTool,
    ReachSearchTool,
    ReachVisitTool,
    ReachYouTubeTranscriptTool,
    get_reach_tools,
)

_CWD = str(Path(__file__).resolve().parent)


# =====================================================================
# 1. Tool schema validity
# =====================================================================


class TestToolSchemas:
    """Every reach tool must have a valid schema for the LLM API."""

    @pytest.fixture(params=[
        ReachSearchTool,
        ReachVisitTool,
        ReachGitHubRepoTool,
        ReachYouTubeTranscriptTool,
        ReachRSSReadTool,
    ])
    def tool(self, request):
        return request.param(cwd=_CWD)

    def test_has_name(self, tool):
        assert tool.name
        assert isinstance(tool.name, str)
        assert tool.name.startswith("reach_")

    def test_has_description(self, tool):
        assert tool.description
        assert isinstance(tool.description, str)

    def test_is_read_only(self, tool):
        assert tool.is_read_only is True

    def test_input_schema_is_valid(self, tool):
        schema = tool.input_schema
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema
        assert isinstance(schema["required"], list)
        assert len(schema["required"]) >= 1

    def test_to_api_schema(self, tool):
        api = tool.to_api_schema()
        assert api["name"] == tool.name
        assert api["description"] == tool.description
        assert api["input_schema"] == tool.input_schema


# =====================================================================
# 2. Registry integration
# =====================================================================


class TestRegistryIntegration:
    def test_get_reach_tools_returns_all_five(self):
        tools = get_reach_tools(cwd=_CWD)
        names = {t.name for t in tools}
        assert names == {
            "reach_search",
            "reach_visit",
            "reach_github_repo",
            "reach_youtube_transcript",
            "reach_rss_read",
        }

    def test_reach_tools_in_get_all_tools(self):
        tools = get_all_tools(cwd=_CWD)
        names = {t.name for t in tools}
        assert "reach_search" in names
        assert "reach_visit" in names
        assert "reach_github_repo" in names
        assert "reach_youtube_transcript" in names
        assert "reach_rss_read" in names


# =====================================================================
# 3. Successful mocked execution
# =====================================================================


class TestReachSearchExecution:
    @patch("devpilot.core.tools.reach.channels.search.requests.post")
    def test_search_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "overall_success": True,
            "items": [
                {"title": "Result One", "url": "https://example.com/1", "snippets": "First result"},
                {"title": "Result Two", "url": "https://example.com/2", "snippets": "Second result"},
            ],
        }
        mock_post.return_value = mock_resp

        import asyncio
        tool = ReachSearchTool(cwd=_CWD)
        with patch.dict("os.environ", {"WEB_SEARCH_ENDPOINT": "http://test/search"}):
            result = asyncio.run(tool.execute(query="test query"))
        assert "Result One" in result
        assert "Result Two" in result


class TestReachVisitExecution:
    @patch("devpilot.core.tools.reach.channels.web.requests.get")
    def test_visit_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = "This is the page content from example.com"
        mock_get.return_value = mock_resp

        import asyncio
        tool = ReachVisitTool(cwd=_CWD)
        result = asyncio.run(tool.execute(url="https://example.com"))
        assert "page content" in result

    def test_visit_invalid_url(self):
        import asyncio
        tool = ReachVisitTool(cwd=_CWD)
        result = asyncio.run(tool.execute(url="not-a-url"))
        assert "http" in result.lower()

    def test_visit_empty_url(self):
        import asyncio
        tool = ReachVisitTool(cwd=_CWD)
        result = asyncio.run(tool.execute(url=""))
        assert "non-empty" in result.lower()


class TestReachGitHubRepoExecution:
    _SAMPLE_GH_OUTPUT = json.dumps({
        "name": "test-repo",
        "description": "A test repo",
        "stargazerCount": 100,
        "defaultBranchRef": {"name": "main"},
        "primaryLanguage": {"name": "Python"},
        "licenseInfo": {"name": "MIT"},
        "repositoryTopics": {"nodes": []},
        "url": "https://github.com/owner/test-repo",
    })

    @patch("devpilot.core.tools.reach.channels.github.is_gh_available", return_value=True)
    @patch("devpilot.core.tools.reach.channels.github.run_safe")
    def test_github_repo_success(self, mock_run, _mock_avail):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=self._SAMPLE_GH_OUTPUT, stderr=""
        )
        import asyncio
        tool = ReachGitHubRepoTool(cwd=_CWD)
        result = asyncio.run(tool.execute(owner_repo="owner/test-repo"))
        assert "test-repo" in result
        assert "100" in result

    @patch("devpilot.core.tools.reach.channels.github.is_gh_available", return_value=False)
    def test_github_repo_gh_missing(self, _mock):
        import asyncio
        tool = ReachGitHubRepoTool(cwd=_CWD)
        result = asyncio.run(tool.execute(owner_repo="owner/test-repo"))
        assert "not installed" in result.lower()


class TestReachYouTubeTranscriptExecution:
    _SAMPLE_META = json.dumps({
        "title": "Test Video",
        "channel": "TestChannel",
        "duration": 300,
        "view_count": 5000,
        "upload_date": "20250601",
        "description": "A test video.",
    })

    @patch("devpilot.core.tools.reach.channels.youtube.is_ytdlp_available", return_value=True)
    @patch("devpilot.core.tools.reach.channels.youtube.run_safe")
    def test_youtube_transcript_success(self, mock_run, _mock_avail):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=self._SAMPLE_META, stderr=""
        )
        import asyncio
        tool = ReachYouTubeTranscriptTool(cwd=_CWD)
        result = asyncio.run(tool.execute(url="https://youtube.com/watch?v=abc"))
        assert "Test Video" in result
        assert "TestChannel" in result

    @patch("devpilot.core.tools.reach.channels.youtube.is_ytdlp_available", return_value=False)
    def test_youtube_ytdlp_missing(self, _mock):
        import asyncio
        tool = ReachYouTubeTranscriptTool(cwd=_CWD)
        result = asyncio.run(tool.execute(url="https://youtube.com/watch?v=abc"))
        assert "not installed" in result.lower()


class TestReachRSSReadExecution:
    _SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Entry One</title>
      <link>https://example.com/1</link>
    </item>
  </channel>
</rss>"""

    @patch("devpilot.core.tools.reach.channels.rss.is_feedparser_available", return_value=True)
    @patch("devpilot.core.tools.reach.channels.rss.requests.get")
    def test_rss_read_success(self, mock_get, _mock_avail):
        # Mock feedparser since it may not be installed
        mock_feedparser = types.ModuleType("feedparser")

        def _parse(content):
            import xml.etree.ElementTree as ET
            root = ET.fromstring(content if isinstance(content, str) else content.decode())
            channel = root.find("channel")
            feed_obj = types.SimpleNamespace(
                title=channel.findtext("title", "") if channel is not None else ""
            )
            entries = []
            for item in (channel.findall("item") if channel is not None else []):
                entries.append(types.SimpleNamespace(
                    title=item.findtext("title", "Untitled"),
                    link=item.findtext("link", ""),
                    published=item.findtext("pubDate", ""),
                    updated="",
                    summary=item.findtext("description", ""),
                ))
            return types.SimpleNamespace(feed=feed_obj, entries=entries, bozo=False)

        mock_feedparser.parse = _parse

        mock_resp = MagicMock()
        mock_resp.content = self._SAMPLE_RSS.encode()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        import asyncio
        tool = ReachRSSReadTool(cwd=_CWD)
        with patch.dict(sys.modules, {"feedparser": mock_feedparser}):
            result = asyncio.run(tool.execute(url="https://example.com/feed"))
        assert "Test Feed" in result
        assert "Entry One" in result

    @patch("devpilot.core.tools.reach.channels.rss.is_feedparser_available", return_value=False)
    def test_rss_feedparser_missing(self, _mock):
        import asyncio
        tool = ReachRSSReadTool(cwd=_CWD)
        result = asyncio.run(tool.execute(url="https://example.com/feed"))
        assert "not installed" in result.lower()

    def test_rss_empty_url(self):
        import asyncio
        tool = ReachRSSReadTool(cwd=_CWD)
        result = asyncio.run(tool.execute(url=""))
        assert "non-empty" in result.lower()
