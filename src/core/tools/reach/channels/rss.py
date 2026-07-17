"""RSS channel — fetch and parse RSS/Atom feeds.

Uses ``requests`` for timeout-controlled fetching, then ``feedparser``
for parsing.  ``feedparser`` is an optional dependency; the command
prints install guidance if it is missing.
"""

from __future__ import annotations

from typing import Any

import requests


_DEFAULT_TIMEOUT = (5, 20)
_DEFAULT_MAX_ENTRIES = 15


def is_feedparser_available() -> bool:
    """Return True if ``feedparser`` is importable."""
    try:
        import feedparser  # noqa: F401
        return True
    except ImportError:
        return False


def fetch(url: str, *, max_entries: int = _DEFAULT_MAX_ENTRIES) -> str:
    """Fetch the RSS/Atom feed at *url* and return formatted entries."""
    if not is_feedparser_available():
        return (
            "[rss] `feedparser` is not installed.\n"
            "Install it: pip install feedparser"
        )

    url = url.strip()
    if not url:
        return "[rss] URL must not be empty."

    try:
        resp = requests.get(url, timeout=_DEFAULT_TIMEOUT)
        resp.raise_for_status()
    except requests.ConnectionError:
        return f"[rss] Connection failed for {url}."
    except requests.Timeout:
        return f"[rss] Request timed out for {url}."
    except requests.HTTPError as exc:
        return f"[rss] HTTP {exc.response.status_code} for {url}."
    except requests.RequestException as exc:
        return f"[rss] Request error: {exc}"

    import feedparser  # safe — is_feedparser_available() already checked

    feed: Any = feedparser.parse(resp.content)

    if feed.bozo and not feed.entries:
        return f"[rss] Failed to parse feed from {url}."

    title = getattr(feed.feed, "title", "") or url
    entries = feed.entries[:max_entries]

    if not entries:
        return f"[rss] No entries found in feed: {title}"

    lines = [f"Feed: {title}", f"Entries: {len(entries)}", ""]
    for idx, entry in enumerate(entries, 1):
        e_title = getattr(entry, "title", "Untitled")
        e_link = getattr(entry, "link", "")
        e_date = getattr(entry, "published", "") or getattr(entry, "updated", "")
        e_summary = getattr(entry, "summary", "")
        if e_summary and len(e_summary) > 200:
            e_summary = e_summary[:200] + "..."

        lines.append(f"{idx}. {e_title}")
        if e_link:
            lines.append(f"   {e_link}")
        if e_date:
            lines.append(f"   {e_date}")
        if e_summary:
            lines.append(f"   {e_summary}")
        lines.append("")

    return "\n".join(lines).strip()
