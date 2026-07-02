"""Search channel — thin CLI wrapper around existing DevPilot web search config.

In Phase 1 this inspects the same ``WEB_SEARCH_ENDPOINT`` environment variable
that ``devpilot.core.tools.web.search.WebSearchTool`` uses.  If the endpoint is
not configured, the command prints setup guidance instead of crashing.
"""

from __future__ import annotations

import os

import requests


_DEFAULT_TIMEOUT = (5, 30)


def _endpoint() -> str | None:
    return os.environ.get("WEB_SEARCH_ENDPOINT") or None


def _api_key() -> str | None:
    return os.environ.get("WEB_SEARCH_API_KEY") or None


def is_configured() -> bool:
    """Return True if the web search endpoint is set."""
    return _endpoint() is not None


def search(query: str, *, max_results: int = 10) -> str:
    """Run a single web search query and return formatted results.

    Uses the same HTTP endpoint that ``WebSearchTool`` uses at runtime.
    Returns a guidance string if the endpoint is not configured.
    """
    endpoint = _endpoint()
    if not endpoint:
        return (
            "[search] Web search is not configured.\n\n"
            "Set the WEB_SEARCH_ENDPOINT environment variable, or run:\n"
            "  devpilot config init --help\n"
            "to configure your LLM and web-search settings."
        )

    payload = {
        "query": query,
        "max_num_results": max_results,
        "provider": os.environ.get("WEB_SEARCH_PROVIDER", "google"),
    }
    headers: dict[str, str] = {"Content-Type": "application/json"}
    key = _api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    try:
        resp = requests.post(
            endpoint, json=payload, headers=headers, timeout=_DEFAULT_TIMEOUT
        )
        resp.raise_for_status()
    except requests.ConnectionError:
        return f"[search] Connection failed to {endpoint}."
    except requests.Timeout:
        return f"[search] Request timed out."
    except requests.HTTPError as exc:
        return f"[search] HTTP {exc.response.status_code} from search endpoint."
    except requests.RequestException as exc:
        return f"[search] Request error: {exc}"

    try:
        data = resp.json()
    except ValueError:
        return "[search] Invalid JSON response from search endpoint."

    if not data.get("overall_success"):
        err = data.get("error_message", "Unknown error")
        return f"[search] Search API error: {err}"

    items = data.get("items", [])
    if not items:
        return f"[search] No results for: {query}"

    lines = [f"Search results for: {query}", ""]
    for idx, item in enumerate(items, 1):
        title = item.get("title", "No Title")
        url = item.get("url", "")
        snippet = item.get("snippets", "")
        lines.append(f"{idx}. {title}")
        if url:
            lines.append(f"   {url}")
        if snippet:
            snip = snippet[:200].strip()
            lines.append(f"   {snip}")
        lines.append("")

    return "\n".join(lines).strip()
