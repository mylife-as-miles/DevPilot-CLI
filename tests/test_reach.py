"""Tests for ``devpilot reach`` — CLI + channels + agent-reach bridge.

All tests use mocked subprocess / network calls.  No real network
access is required.
"""

from __future__ import annotations

import ast
import inspect
import json
import os
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Bootstrap devpilot import (same as conftest.py) ──────────────────
import importlib.util
import sys

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

from typer.testing import CliRunner

from devpilot.cli.commands.reach_cmd import reach_app
from devpilot.core.tools.reach import agent_reach_bridge
from devpilot.core.tools.reach import subprocess_utils
from devpilot.core.tools.reach.channels import github as github_channel
from devpilot.core.tools.reach.channels import rss as rss_channel
from devpilot.core.tools.reach.channels import web as web_channel
from devpilot.core.tools.reach.channels import youtube as youtube_channel

runner = CliRunner()


# =====================================================================
# 1. CLI help
# =====================================================================


class TestReachHelp:
    def test_reach_help(self):
        result = runner.invoke(reach_app, ["--help"])
        assert result.exit_code == 0
        assert "DevPilot Reach" in result.output

    def test_agent_reach_help(self):
        result = runner.invoke(reach_app, ["agent-reach", "--help"])
        assert result.exit_code == 0
        assert "Agent Reach" in result.output


# =====================================================================
# 2. devpilot reach doctor
# =====================================================================


class TestReachDoctor:
    @patch("devpilot.core.tools.reach.doctor.shutil.which", return_value=None)
    @patch("devpilot.core.tools.reach.doctor.subprocess.check_output", side_effect=FileNotFoundError)
    def test_doctor_does_not_crash(self, _mock_check, _mock_which):
        result = runner.invoke(reach_app, ["doctor"])
        # Should not crash — exit code can be 0 or 1 depending on missing deps
        assert result.exit_code in (0, 1)
        assert "DevPilot Reach doctor" in result.output


# =====================================================================
# 3. agent-reach status when missing
# =====================================================================


class TestAgentReachStatus:
    @patch.object(agent_reach_bridge, "is_installed", return_value=False)
    def test_status_when_missing(self, _mock):
        result = runner.invoke(reach_app, ["agent-reach", "status"])
        assert result.exit_code == 0
        assert "not installed" in result.output

    @patch.object(agent_reach_bridge, "is_installed", return_value=True)
    def test_status_when_installed(self, _mock):
        result = runner.invoke(reach_app, ["agent-reach", "status"])
        assert result.exit_code == 0
        assert "installed" in result.output


# =====================================================================
# 4. agent-reach install-help
# =====================================================================


class TestAgentReachInstallHelp:
    def test_install_help_prints_url(self):
        result = runner.invoke(reach_app, ["agent-reach", "install-help"])
        assert result.exit_code == 0
        assert "帮我安装 Agent Reach" in result.output
        assert "install.md" in result.output

    def test_install_help_includes_safe_mode(self):
        result = runner.invoke(reach_app, ["agent-reach", "install-help"])
        assert "--safe" in result.output

    def test_install_help_includes_openclaw(self):
        result = runner.invoke(reach_app, ["agent-reach", "install-help"])
        assert "openclaw" in result.output.lower()


# =====================================================================
# 5. agent-reach update-help
# =====================================================================


class TestAgentReachUpdateHelp:
    def test_update_help_prints_url(self):
        result = runner.invoke(reach_app, ["agent-reach", "update-help"])
        assert result.exit_code == 0
        assert "帮我更新 Agent Reach" in result.output
        assert "update.md" in result.output


# =====================================================================
# 6. Mocked gh wrapper
# =====================================================================


class TestGitHubChannel:
    _SAMPLE_GH_OUTPUT = json.dumps({
        "name": "openai-python",
        "description": "The official Python library for the OpenAI API",
        "stargazerCount": 25000,
        "defaultBranchRef": {"name": "main"},
        "primaryLanguage": {"name": "Python"},
        "licenseInfo": {"name": "Apache License 2.0", "spdxId": "Apache-2.0"},
        "repositoryTopics": {"nodes": [{"topic": {"name": "python"}}]},
        "url": "https://github.com/openai/openai-python",
    })

    @patch.object(github_channel, "is_gh_available", return_value=True)
    @patch("devpilot.core.tools.reach.channels.github.run_safe")
    def test_repo_view(self, mock_run, _mock_avail):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=self._SAMPLE_GH_OUTPUT, stderr=""
        )
        result = github_channel.repo_view("openai/openai-python")
        assert "openai-python" in result
        assert "25000" in result
        assert "Python" in result

    @patch.object(github_channel, "is_gh_available", return_value=False)
    def test_repo_view_gh_missing(self, _mock):
        result = github_channel.repo_view("openai/openai-python")
        assert "not installed" in result.lower()

    def test_invalid_owner_repo(self):
        with patch.object(github_channel, "is_gh_available", return_value=True):
            result = github_channel.repo_view("bad-format")
            assert "Invalid" in result


# =====================================================================
# 7. Mocked yt-dlp wrapper
# =====================================================================


class TestYouTubeChannel:
    _SAMPLE_META = json.dumps({
        "title": "Test Video",
        "channel": "TestChannel",
        "duration": 120,
        "view_count": 1000,
        "upload_date": "20250101",
        "description": "A test video.",
    })

    @patch.object(youtube_channel, "is_ytdlp_available", return_value=True)
    @patch("devpilot.core.tools.reach.channels.youtube.run_safe")
    def test_fetch_metadata(self, mock_run, _mock_avail):
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=self._SAMPLE_META, stderr=""
        )
        result = youtube_channel.fetch("https://youtube.com/watch?v=test")
        assert "Test Video" in result
        assert "TestChannel" in result

    @patch.object(youtube_channel, "is_ytdlp_available", return_value=False)
    def test_fetch_ytdlp_missing(self, _mock):
        result = youtube_channel.fetch("https://youtube.com/watch?v=test")
        assert "not installed" in result.lower()


# =====================================================================
# 8. Mocked RSS parsing
# =====================================================================


class TestRSSChannel:
    _SAMPLE_RSS = textwrap.dedent("""\
        <?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>Test Feed</title>
            <item>
              <title>Article One</title>
              <link>https://example.com/1</link>
              <pubDate>Mon, 01 Jan 2025 00:00:00 GMT</pubDate>
              <description>First article summary.</description>
            </item>
            <item>
              <title>Article Two</title>
              <link>https://example.com/2</link>
            </item>
          </channel>
        </rss>
    """)

    @patch("devpilot.core.tools.reach.channels.rss.is_feedparser_available", return_value=True)
    @patch("devpilot.core.tools.reach.channels.rss.requests.get")
    def test_fetch_rss(self, mock_get, _mock_avail):
        # feedparser may not be installed, so provide a mock
        import types
        mock_feedparser = types.ModuleType("feedparser")

        # Minimal feedparser.parse implementation for test
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
            result = types.SimpleNamespace(feed=feed_obj, entries=entries, bozo=False)
            return result

        mock_feedparser.parse = _parse

        mock_resp = MagicMock()
        mock_resp.content = self._SAMPLE_RSS.encode()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        with patch.dict(sys.modules, {"feedparser": mock_feedparser}):
            result = rss_channel.fetch("https://hnrss.org/frontpage")
        assert "Test Feed" in result
        assert "Article One" in result
        assert "Article Two" in result

    @patch("devpilot.core.tools.reach.channels.rss.is_feedparser_available", return_value=False)
    def test_fetch_feedparser_missing(self, _mock):
        result = rss_channel.fetch("https://hnrss.org/frontpage")
        assert "not installed" in result.lower()


# =====================================================================
# 9. No command uses shell=True — source code audit
# =====================================================================


class TestNoShellTrue:
    """Walk the reach source tree and assert no subprocess call uses shell=True."""

    _REACH_PKG = Path(__file__).resolve().parent.parent / "src" / "core" / "tools" / "reach"

    def _python_files(self):
        for root, _dirs, files in os.walk(self._REACH_PKG):
            for f in files:
                if f.endswith(".py"):
                    yield Path(root) / f

    def test_no_shell_true_in_source(self):
        violations: list[str] = []
        for path in self._python_files():
            source = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source, filename=str(path))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    for kw in node.keywords:
                        if kw.arg == "shell" and isinstance(kw.value, ast.Constant):
                            if kw.value.value is True:
                                violations.append(
                                    f"{path.relative_to(self._REACH_PKG)}:{node.lineno}"
                                )
        assert not violations, f"shell=True found in: {violations}"


# =====================================================================
# 10. Web channel — Jina URL normalisation
# =====================================================================


class TestWebChannel:
    def test_normalise_plain_url(self):
        result = web_channel._normalise_jina_url("https://example.com/page")
        assert result == "https://r.jina.ai/https://example.com/page"

    def test_normalise_already_wrapped(self):
        result = web_channel._normalise_jina_url(
            "https://r.jina.ai/https://example.com"
        )
        assert result == "https://r.jina.ai/https://example.com"

    def test_normalise_rejects_no_scheme(self):
        with pytest.raises(ValueError, match="http"):
            web_channel._normalise_jina_url("example.com")

    def test_normalise_rejects_empty(self):
        with pytest.raises(ValueError, match="empty"):
            web_channel._normalise_jina_url("")


# =====================================================================
# 11. Providers listing
# =====================================================================


class TestProviders:
    @patch("devpilot.core.tools.reach.providers.shutil.which", return_value=None)
    def test_providers_lists_channels(self, _mock):
        result = runner.invoke(reach_app, ["providers"])
        assert result.exit_code == 0
        assert "web:" in result.output
        assert "search:" in result.output
        assert "github:" in result.output
        assert "youtube:" in result.output
        assert "rss:" in result.output
        assert "agent-reach:" in result.output
