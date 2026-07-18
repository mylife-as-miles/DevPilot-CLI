"""Prompt-context compression hooks."""

from __future__ import annotations

import json
from pathlib import Path

from .bridge import is_headroom_available
from .runner import compression_dir, conservative_compress_text, context_cache_path, ensure_compression_workspace


def maybe_compress_prompt_context(
    text: str,
    *,
    project_root: str | Path,
    compression_config: object | None,
    kind: str,
) -> str:
    if not text:
        return ""
    cfg = compression_config
    if cfg is None or not getattr(cfg, "enabled", False):
        return text
    if kind in {"reach"} and not getattr(cfg, "compress_reach_evidence", True):
        return text
    if kind in {"memory", "learned_memory"} and not getattr(cfg, "compress_memory_context", True):
        return text

    max_chars = int(getattr(cfg, "max_context_chars", 6000) or 6000)
    if len(text) <= max_chars:
        return text
    if not is_headroom_available(project_root):
        return text

    compressed = conservative_compress_text(text, max_chars=max_chars)
    _append_cache(project_root, kind=kind, original_chars=len(text), compressed_chars=len(compressed))
    return compressed


def _append_cache(project_root: str | Path, *, kind: str, original_chars: int, compressed_chars: int) -> None:
    try:
        root = Path(project_root).resolve()
        ensure_compression_workspace(root)
        with context_cache_path(root).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "kind": kind,
                "original_chars": original_chars,
                "compressed_chars": compressed_chars,
                "workspace": str(compression_dir(root)),
            }, sort_keys=True) + "\n")
    except OSError:
        return
