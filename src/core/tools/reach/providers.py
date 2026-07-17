"""``devpilot reach providers`` — list available Reach data sources."""

from __future__ import annotations

import os
import shutil


def list_providers() -> str:
    """Return a formatted provider listing."""
    lines = ["DevPilot Reach providers\n"]

    # web
    browse_ep = os.environ.get("WEB_BROWSE_ENDPOINT")
    if browse_ep:
        lines.append(f"  web:          devpilot browse endpoint ({browse_ep})")
    else:
        jina_key = os.environ.get("JINA_API_KEY")
        tag = "jina (authenticated)" if jina_key else "jina (anonymous)"
        lines.append(f"  web:          {tag}")

    # search
    search_ep = os.environ.get("WEB_SEARCH_ENDPOINT")
    if search_ep:
        provider = os.environ.get("WEB_SEARCH_PROVIDER", "google")
        lines.append(f"  search:       devpilot web search ({provider})")
    else:
        lines.append("  search:       unavailable (WEB_SEARCH_ENDPOINT not set)")

    # github
    if shutil.which("gh"):
        lines.append("  github:       gh CLI")
    else:
        lines.append("  github:       unavailable (gh not installed)")

    # youtube
    if shutil.which("yt-dlp"):
        lines.append("  youtube:      yt-dlp")
    else:
        lines.append("  youtube:      unavailable (yt-dlp not installed)")

    # rss
    try:
        import feedparser  # noqa: F401
        lines.append("  rss:          feedparser")
    except ImportError:
        lines.append("  rss:          unavailable (feedparser not installed)")

    # agent-reach
    if shutil.which("agent-reach"):
        lines.append("  agent-reach:  installed")
    else:
        lines.append("  agent-reach:  not installed (optional)")

    return "\n".join(lines)
