"""Prompt-context helpers for optional MemPalace recall."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .bridge import is_mempalace_available
from .runner import config_path, context_cache_path, is_initialized, wake_up


def build_long_term_memory_section(
    project_root: str | Path,
    *,
    query: str = "",
    max_chars: int = 4000,
    max_snippets: int = 5,
) -> str:
    """Return a compact prompt section from MemPalace, or ``""`` if unavailable."""

    root = Path(project_root).resolve()
    if not is_initialized(root) or not is_mempalace_available(root):
        return ""

    result = wake_up(project_root=root, query=query or None, max_chars=max_chars, timeout=30)
    if not result.ok and not result.stdout.strip():
        return ""

    snippets = _snippets(result.stdout, limit=max_snippets)
    if not snippets:
        return ""

    _append_cache(root, query=query, snippets=snippets)
    lines = [
        "## Long-Term Memory Context",
        "",
        "Relevant memories recovered from MemPalace:",
    ]
    lines.extend(f"- {snippet}" for snippet in snippets)
    return "\n".join(lines)


def _snippets(text: str, *, limit: int) -> list[str]:
    clean_lines: list[str] = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line.strip())
        if not line:
            continue
        if line.startswith("=") or line.lower().startswith("wake-up text"):
            continue
        clean_lines.append(_compact(line, 220))
    return clean_lines[: max(0, limit)]


def _append_cache(root: Path, *, query: str, snippets: list[str]) -> None:
    try:
        if not config_path(root).exists():
            return
        path = context_cache_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"query": query, "snippets": snippets}, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        return


def _compact(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."
