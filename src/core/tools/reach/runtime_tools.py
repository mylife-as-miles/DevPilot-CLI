"""Runtime tools that expose DevPilot Reach channels to the agent loop.

Each tool wraps one of the Phase 1 channel functions, sets
``is_read_only = True``, and returns compact evidence with source URLs.

These tools never mutate files, accounts, repos, browser sessions,
or external services.  They never use ``shell=True``.  They never
access cookie/login platforms.
"""

from __future__ import annotations

import asyncio
from typing import Any

from ..base import Tool
from .channels import github as github_channel
from .channels import rss as rss_channel
from .channels import search as search_channel
from .channels import web as web_channel
from .channels import youtube as youtube_channel


# =====================================================================
# Reach Base Tool
# =====================================================================


class ReachBaseTool(Tool):
    """Base class for all Reach tools to share constructor and evidence persistence."""

    def __init__(
        self,
        *,
        cwd: str,
        workspace_dir: str | None = None,
        config: Any = None,
        **kwargs: Any,
    ):
        super().__init__(cwd=cwd, workspace_dir=workspace_dir, **kwargs)
        self.config = config

    def _save_evidence(
        self,
        *,
        tool_name: str,
        source: str,
        query: str,
        content: str,
        title: str | None = None,
        summary: str | None = None,
    ) -> None:
        """Call save_reach_evidence if workspace_dir is active."""
        if not self.workspace_dir:
            return

        cycle_id = None
        hypothesis_id = None
        if self.config:
            cycle_id = getattr(self.config, "cycle_id", None)
            hypothesis_id = getattr(self.config, "node_id", None)

        from .evidence import save_reach_evidence
        save_reach_evidence(
            self.workspace_dir,
            tool_name=tool_name,
            source=source,
            query=query,
            content=content,
            title=title,
            summary=summary,
            cycle_id=cycle_id,
            hypothesis_id=hypothesis_id,
        )


# =====================================================================
# reach_search
# =====================================================================


class ReachSearchTool(ReachBaseTool):
    """Web search via the configured DevPilot search endpoint."""

    name = "reach_search"
    description = (
        "Performs a web search query using the configured DevPilot search "
        "endpoint and returns compact results with URLs.\n\n"
        "Use this when you need to search the web for information, papers, "
        "documentation, or prior work relevant to a hypothesis."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to run.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default 10).",
            },
        },
        "required": ["query"],
    }
    is_read_only = True

    async def execute(self, **kwargs: Any) -> str:
        query = kwargs.get("query", "")
        if not query or not str(query).strip():
            return "[reach_search] query must be a non-empty string."
        max_results = kwargs.get("max_results", 10)
        try:
            max_results = int(max_results)
        except (TypeError, ValueError):
            max_results = 10
        result = await asyncio.to_thread(
            search_channel.search, str(query).strip(), max_results=max_results
        )

        # Save to evidence store
        self._save_evidence(
            tool_name=self.name,
            source="web_search",
            query=str(query).strip(),
            content=result,
        )

        return self.process_result(result)


# =====================================================================
# reach_visit
# =====================================================================


class ReachVisitTool(ReachBaseTool):
    """Fetch a URL and return readable text via Jina Reader."""

    name = "reach_visit"
    description = (
        "Fetches a URL via the Jina Reader API and returns clean, "
        "readable text content.\n\n"
        "Use this to read the contents of a web page, documentation site, "
        "blog post, or paper. The tool never modifies the target resource."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to visit (must start with http:// or https://).",
            },
            "max_chars": {
                "type": "integer",
                "description": "Maximum characters to return (default 8000).",
            },
        },
        "required": ["url"],
    }
    is_read_only = True

    async def execute(self, **kwargs: Any) -> str:
        url = kwargs.get("url", "")
        if not url or not str(url).strip():
            return "[reach_visit] url must be a non-empty string."
        max_chars = kwargs.get("max_chars", 8000)
        try:
            max_chars = int(max_chars)
        except (TypeError, ValueError):
            max_chars = 8000
        try:
            result = await asyncio.to_thread(
                web_channel.visit, str(url).strip(), max_chars=max_chars
            )
        except ValueError as exc:
            return f"[reach_visit] {exc}"

        # Extract title if present in Jina's output format
        title = None
        for line in result.splitlines()[:5]:
            if line.lower().startswith("title:"):
                title = line[6:].strip()
                break

        self._save_evidence(
            tool_name=self.name,
            source=str(url).strip(),
            query=str(url).strip(),
            content=result,
            title=title,
        )

        return self.process_result(result)


# =====================================================================
# reach_github_repo
# =====================================================================


class ReachGitHubRepoTool(ReachBaseTool):
    """Fetch GitHub repository metadata via the ``gh`` CLI."""

    name = "reach_github_repo"
    description = (
        "Fetches GitHub repository metadata (stars, language, license, "
        "topics, description) using the gh CLI.\n\n"
        "Requires ``gh`` to be installed and authenticated. "
        "Returns a compact summary. Read-only — never modifies the repo."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "owner_repo": {
                "type": "string",
                "description": (
                    "Repository identifier in owner/repo format "
                    "(e.g. 'openai/openai-python')."
                ),
            },
        },
        "required": ["owner_repo"],
    }
    is_read_only = True

    async def execute(self, **kwargs: Any) -> str:
        owner_repo = kwargs.get("owner_repo", "")
        if not owner_repo or not str(owner_repo).strip():
            return "[reach_github_repo] owner_repo must be a non-empty string."
        result = await asyncio.to_thread(
            github_channel.repo_view, str(owner_repo).strip()
        )

        title = None
        for line in result.splitlines()[:5]:
            if line.lower().startswith("repository:"):
                title = line[11:].strip()
                break

        self._save_evidence(
            tool_name=self.name,
            source=f"https://github.com/{str(owner_repo).strip()}",
            query=str(owner_repo).strip(),
            content=result,
            title=title,
        )

        return self.process_result(result)


# =====================================================================
# reach_youtube_transcript
# =====================================================================


class ReachYouTubeTranscriptTool(ReachBaseTool):
    """Fetch YouTube video metadata and transcript without downloading media."""

    name = "reach_youtube_transcript"
    description = (
        "Fetches YouTube video metadata (title, channel, duration, views) "
        "and auto-generated subtitles/transcript without downloading any "
        "video or audio.\n\n"
        "Requires ``yt-dlp`` to be installed.  Always uses --skip-download."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "YouTube video URL.",
            },
        },
        "required": ["url"],
    }
    is_read_only = True

    async def execute(self, **kwargs: Any) -> str:
        url = kwargs.get("url", "")
        if not url or not str(url).strip():
            return "[reach_youtube_transcript] url must be a non-empty string."
        result = await asyncio.to_thread(
            youtube_channel.fetch, str(url).strip()
        )

        title = None
        for line in result.splitlines()[:5]:
            if line.lower().startswith("title:"):
                title = line[6:].strip()
                break

        self._save_evidence(
            tool_name=self.name,
            source=str(url).strip(),
            query=str(url).strip(),
            content=result,
            title=title,
        )

        return self.process_result(result)


# =====================================================================
# reach_rss_read
# =====================================================================


class ReachRSSReadTool(ReachBaseTool):
    """Fetch and parse an RSS/Atom feed."""

    name = "reach_rss_read"
    description = (
        "Fetches an RSS or Atom feed and returns the most recent entries "
        "with titles, links, dates, and summaries.\n\n"
        "Requires ``feedparser`` to be installed.  Read-only — never "
        "modifies the feed source."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "RSS or Atom feed URL.",
            },
            "max_entries": {
                "type": "integer",
                "description": "Maximum number of entries to return (default 15).",
            },
        },
        "required": ["url"],
    }
    is_read_only = True

    async def execute(self, **kwargs: Any) -> str:
        url = kwargs.get("url", "")
        if not url or not str(url).strip():
            return "[reach_rss_read] url must be a non-empty string."
        max_entries = kwargs.get("max_entries", 15)
        try:
            max_entries = int(max_entries)
        except (TypeError, ValueError):
            max_entries = 15
        result = await asyncio.to_thread(
            rss_channel.fetch, str(url).strip(), max_entries=max_entries
        )

        title = None
        for line in result.splitlines()[:5]:
            if line.lower().startswith("feed:"):
                title = line[5:].strip()
                break

        self._save_evidence(
            tool_name=self.name,
            source=str(url).strip(),
            query=str(url).strip(),
            content=result,
            title=title,
        )

        return self.process_result(result)


# =====================================================================
# Registry helper
# =====================================================================


_ALL_REACH_TOOL_CLASSES = [
    ReachSearchTool,
    ReachVisitTool,
    ReachGitHubRepoTool,
    ReachYouTubeTranscriptTool,
    ReachRSSReadTool,
]


def get_reach_tools(
    *, cwd: str, workspace_dir: str | None = None, config: Any = None
) -> list[Tool]:
    """Return all Reach runtime tools.

    Each tool gracefully handles missing external dependencies at
    execution time (returns a helpful message rather than crashing),
    so it is always safe to register them.
    """
    return [
        cls(cwd=cwd, workspace_dir=workspace_dir, config=config)
        for cls in _ALL_REACH_TOOL_CLASSES
    ]
