"""Compression workspace and text compression helpers."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ..._app import CONFIG_DIR_NAME
from .bridge import find_project_root, run_headroom, run_headroom_python
from .types import RunResult


MANIFEST_FILE = "compression_manifest.jsonl"
CACHE_FILE = "compressed_context_cache.jsonl"

_HEADROOM_COMPRESS_SCRIPT = r"""
import json
import sys
from pathlib import Path

from headroom import compress
from headroom.compress import CompressConfig

path = Path(sys.argv[1])
max_chars = int(sys.argv[2])
text = path.read_text(encoding="utf-8", errors="replace")
messages = [{"role": "user", "content": text}]
result = compress(
    messages,
    model="claude-sonnet-4-5-20250929",
    config=CompressConfig(
        compress_user_messages=True,
        compress_system_messages=False,
        protect_recent=0,
        kompress_model="disabled",
        min_tokens_to_compress=32,
    ),
)
content = result.messages[0].get("content", "")
if isinstance(content, list):
    content = "\n".join(str(part) for part in content)
if len(content) > max_chars:
    content = content[: max(0, max_chars - 14)].rstrip() + "\n\n[truncated]"
print(content)
"""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def compression_dir(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / CONFIG_DIR_NAME / "compression"


def reports_dir(project_root: str | Path) -> Path:
    return compression_dir(project_root) / "reports"


def manifest_path(project_root: str | Path) -> Path:
    return compression_dir(project_root) / MANIFEST_FILE


def context_cache_path(project_root: str | Path) -> Path:
    return compression_dir(project_root) / CACHE_FILE


def ensure_compression_workspace(project_root: str | Path) -> Path:
    root = Path(project_root).resolve()
    out = compression_dir(root)
    reports_dir(root).mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    manifest_path(root).touch(exist_ok=True)
    context_cache_path(root).touch(exist_ok=True)
    return out


def append_manifest(project_root: str | Path, record: dict[str, object]) -> None:
    root = Path(project_root).resolve()
    ensure_compression_workspace(root)
    payload = {"created_at": utc_now_iso(), **record}
    with manifest_path(root).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def compress_text_file(
    path: str | Path,
    *,
    project_root: str | Path | None = None,
    max_chars: int = 6000,
    timeout: int = 300,
) -> RunResult:
    root = find_project_root(project_root)
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = (root / file_path).resolve()
    if not file_path.is_file():
        return RunResult(
            argv=[],
            returncode=2,
            stdout="",
            stderr=f"File not found: {file_path}",
            cwd=str(root),
            source="devpilot",
            error="missing-file",
        )

    result = run_headroom_python(
        _HEADROOM_COMPRESS_SCRIPT,
        [str(file_path), str(max_chars)],
        cwd=root,
        timeout=timeout,
    )
    if result.ok and result.stdout.strip():
        append_manifest(root, {"action": "text", "source": str(file_path), "bytes": file_path.stat().st_size})
        return result

    text = file_path.read_text(encoding="utf-8", errors="replace")
    compact = conservative_compress_text(text, max_chars=max_chars)
    stderr = result.stderr.strip()
    if result.error == "missing" or "ModuleNotFoundError" in stderr or "No module named" in stderr:
        stderr = (stderr + "\n" if stderr else "") + "Headroom unavailable; used DevPilot conservative compression fallback. Run `devpilot compress install --dry-run` for setup guidance."
        code = 0
    else:
        code = result.returncode
    append_manifest(root, {"action": "text-fallback", "source": str(file_path), "bytes": file_path.stat().st_size})
    return RunResult(
        argv=result.argv,
        returncode=code,
        stdout=compact,
        stderr=stderr,
        cwd=result.cwd,
        source=result.source,
        error=None if code == 0 else result.error,
        timed_out=result.timed_out,
    )


def compress_text_content(
    text: str,
    *,
    project_root: str | Path,
    max_chars: int = 6000,
    label: str = "context",
) -> str:
    if len(text) <= max_chars:
        return text
    compact = conservative_compress_text(text, max_chars=max_chars)
    append_manifest(project_root, {"action": "prompt-context-fallback", "label": label, "original_chars": len(text), "compressed_chars": len(compact)})
    return compact


def status_lines(project_root: str | Path) -> list[str]:
    root = Path(project_root).resolve()
    ensure_compression_workspace(root)
    result = run_headroom(["--version"], cwd=root, timeout=30)
    lines = ["DevPilot Compression status", ""]
    lines.append(f"workspace: {compression_dir(root)}")
    lines.append(f"reports: {reports_dir(root)}")
    if result.ok:
        lines.append(f"headroom: available via {result.source} ({result.stdout.strip() or 'version unknown'})")
    else:
        lines.append("headroom: not fully available")
        lines.append("hint: run `devpilot compress install --dry-run` for setup guidance")
    lines.append("proxy: not required for file/session compression")
    return lines


def conservative_compress_text(text: str, *, max_chars: int) -> str:
    clean_lines = [line.rstrip() for line in str(text).splitlines()]
    selected: list[str] = []
    seen_blank = False
    important_patterns = (
        "http://",
        "https://",
        "hypothesis",
        "source",
        "error",
        "failed",
        "failure",
        "traceback",
        "assert",
        "test_",
        "exit code",
        "decision",
        "merged",
        "pruned",
        "score",
        "result",
    )
    for index, line in enumerate(clean_lines):
        stripped = line.strip()
        lower = stripped.lower()
        keep = (
            index < 40
            or stripped.startswith("#")
            or stripped.startswith("-")
            or any(pattern in lower for pattern in important_patterns)
        )
        if not stripped:
            if seen_blank:
                continue
            seen_blank = True
            keep = True
        else:
            seen_blank = False
        if keep:
            selected.append(line)
    if len(clean_lines) > 80:
        tail = [line for line in clean_lines[-30:] if line.strip()]
        if tail:
            selected.extend(["", "## Tail", *tail])
    compact = "\n".join(selected).strip()
    compact = re.sub(r"\n{3,}", "\n\n", compact)
    if len(compact) <= max_chars:
        return compact
    suffix = "\n\n[truncated]"
    return compact[: max(0, max_chars - len(suffix))].rstrip() + suffix
