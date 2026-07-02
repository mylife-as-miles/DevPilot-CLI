"""Web channel — fetch a URL and return readable text.

Uses the Jina Reader API (``https://r.jina.ai/``) as the default backend.
If ``WEB_BROWSE_ENDPOINT`` is configured, that is checked first for the
``devpilot reach doctor`` report, but the CLI ``visit`` command always uses
Jina Reader for simplicity in Phase 1.
"""

from __future__ import annotations

import os

import requests


_JINA_READER_PREFIX = "https://r.jina.ai/"
_DEFAULT_TIMEOUT = (5, 30)  # (connect, read) seconds
_DEFAULT_MAX_CHARS = 8000


def _normalise_jina_url(url: str) -> str:
    """Wrap *url* in the Jina Reader prefix exactly once.

    Validates that the input starts with ``http://`` or ``https://``.
    Raises ``ValueError`` for invalid URLs.
    """
    stripped = url.strip()
    if not stripped:
        raise ValueError("URL must not be empty.")
    if not (stripped.startswith("http://") or stripped.startswith("https://")):
        raise ValueError(
            f"URL must start with http:// or https:// (got {stripped!r})."
        )
    if stripped.startswith(_JINA_READER_PREFIX):
        return stripped
    return _JINA_READER_PREFIX + stripped


def visit(url: str, *, max_chars: int = _DEFAULT_MAX_CHARS) -> str:
    """Fetch *url* via Jina Reader and return cleaned text.

    Truncates the response to *max_chars* characters.
    """
    reader_url = _normalise_jina_url(url)
    headers = {"Accept": "text/plain"}
    jina_key = os.environ.get("JINA_API_KEY")
    if jina_key:
        headers["Authorization"] = f"Bearer {jina_key}"

    try:
        resp = requests.get(reader_url, headers=headers, timeout=_DEFAULT_TIMEOUT)
        resp.raise_for_status()
    except requests.ConnectionError:
        return f"[web] Connection failed for {url}."
    except requests.Timeout:
        return f"[web] Request timed out for {url}."
    except requests.HTTPError as exc:
        return f"[web] HTTP {exc.response.status_code} for {url}."
    except requests.RequestException as exc:
        return f"[web] Request error: {exc}"

    text = resp.text.strip()
    if not text:
        return f"[web] Empty content from {url}."
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n\n... [truncated at {max_chars} chars]"
    return text


def jina_available() -> bool:
    """Quick connectivity check to the Jina Reader endpoint."""
    try:
        resp = requests.head(
            _JINA_READER_PREFIX,
            timeout=(3, 5),
            allow_redirects=True,
        )
        return resp.status_code < 500
    except Exception:
        return False


def browse_endpoint_configured() -> bool:
    """Return True if ``WEB_BROWSE_ENDPOINT`` is set in the environment."""
    return bool(os.environ.get("WEB_BROWSE_ENDPOINT"))
