"""Glob tool — find files by name pattern.
Description ported from Claude Code's GlobTool."""

from __future__ import annotations

import os
import pathlib
from typing import Any

from .base import Tool


class GlobTool(Tool):
    name = "Glob"
    description = (
        "Fast file pattern matching tool that works with any codebase size.\n"
        "- Supports glob patterns like \"**/*.py\" or \"src/**/*.ts\"\n"
        "- Returns matching file paths sorted by modification time\n"
        "- Use this tool when you need to find files by name patterns\n"
        "- When you are doing an open-ended search that may require multiple "
        "rounds of globbing and grepping, use the Executor tool instead"
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": 'Glob pattern to match (e.g. "**/*.py", "src/**/*.ts").',
            },
            "path": {
                "type": "string",
                "description": "Directory to search in. Default: working directory.",
            },
        },
        "required": ["pattern"],
    }
    is_read_only = True
    max_result_chars = 50_000

    async def execute(self, **kwargs: Any) -> str:
        pattern: str = kwargs["pattern"]
        path: str = kwargs.get("path", self.cwd)

        if not os.path.isabs(path):
            path = os.path.join(self.cwd, path)

        from .path_guard import check_path_allowed
        blocked = check_path_allowed(path)
        if blocked:
            return f"BLOCKED: {blocked}"

        base = pathlib.Path(path)
        if not base.exists():
            return f"Error: Directory not found: {path}"
        if not base.is_dir():
            return f"Error: {path} is not a directory."

        try:
            matches = list(base.glob(pattern))
        except Exception as e:
            return f"Error during glob: {e}"

        # Filter out hidden/VCS directories
        skip_dirs = {".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv"}
        filtered = []
        for m in matches:
            parts = m.relative_to(base).parts
            if any(p in skip_dirs for p in parts):
                continue
            if m.is_file():
                filtered.append(m)

        # Sort by modification time (newest first)
        filtered.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # Limit to 100
        max_files = 100
        truncated = len(filtered) > max_files
        filtered = filtered[:max_files]

        # Format output: relative paths
        lines = [str(m.relative_to(base)) for m in filtered]

        result = "\n".join(lines)
        if truncated:
            result += f"\n\n[Showing first {max_files} of more matches]"

        if not lines:
            result = f"No files matching '{pattern}' found in {path}."

        return result
