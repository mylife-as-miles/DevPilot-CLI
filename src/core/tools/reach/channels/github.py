"""GitHub channel — fetch repository info via the ``gh`` CLI.

Requires ``gh`` (GitHub CLI) to be installed and authenticated.
Uses ``shell=False`` and a timeout.
"""

from __future__ import annotations

import json

from ..subprocess_utils import is_available, run_safe


_GH_BIN = "gh"

_REPO_JSON_FIELDS = (
    "name,description,stargazerCount,defaultBranchRef,"
    "primaryLanguage,licenseInfo,repositoryTopics,url"
)


def is_gh_available() -> bool:
    """Return True if ``gh`` is on PATH."""
    return is_available(_GH_BIN)


def repo_view(owner_repo: str, *, timeout: int = 15) -> str:
    """Fetch repo metadata for *owner_repo* (e.g. ``openai/openai-python``).

    Returns a compact, human-readable summary.
    """
    if not is_gh_available():
        return (
            "[github] `gh` CLI is not installed.\n"
            "Install it from https://cli.github.com/ and run `gh auth login`."
        )

    parts = owner_repo.strip().split("/")
    if len(parts) != 2 or not all(parts):
        return f"[github] Invalid owner/repo format: {owner_repo!r}. Expected owner/repo."

    cmd = [_GH_BIN, "repo", "view", owner_repo, "--json", _REPO_JSON_FIELDS]
    try:
        result = run_safe(cmd, timeout=timeout)
    except FileNotFoundError:
        return "[github] `gh` binary not found despite being on PATH."
    except Exception as exc:
        return f"[github] Failed to run gh: {type(exc).__name__}: {exc}"

    if result.returncode != 0:
        err = (result.stderr or "").strip()
        return f"[github] gh repo view failed (exit {result.returncode}): {err}"

    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return "[github] Could not parse gh output as JSON."

    return _format_repo(data)


def _format_repo(data: dict) -> str:
    """Render repo JSON into compact readable text."""
    name = data.get("name", "?")
    desc = data.get("description", "")
    stars = data.get("stargazerCount", "?")
    url = data.get("url", "")

    branch_ref = data.get("defaultBranchRef") or {}
    branch = branch_ref.get("name", "?")

    lang_info = data.get("primaryLanguage") or {}
    lang = lang_info.get("name", "—")

    license_info = data.get("licenseInfo") or {}
    lic = license_info.get("name") or license_info.get("spdxId") or "—"

    topics_raw = data.get("repositoryTopics") or {}
    # gh returns {nodes: [{topic: {name: ...}}, ...]}
    nodes = topics_raw.get("nodes") or []
    topics = [n.get("topic", {}).get("name", "") for n in nodes if n.get("topic")]
    topics_str = ", ".join(topics[:10]) if topics else "—"

    lines = [
        f"Repository: {name}",
        f"URL:        {url}",
        f"Stars:      {stars}",
        f"Language:   {lang}",
        f"License:    {lic}",
        f"Branch:     {branch}",
        f"Topics:     {topics_str}",
    ]
    if desc:
        lines.insert(1, f"About:      {desc}")
    return "\n".join(lines)
