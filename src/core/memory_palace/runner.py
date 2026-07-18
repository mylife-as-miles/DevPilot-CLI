"""Project-local MemPalace command helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..._app import CONFIG_DIR_NAME
from .bridge import find_project_root, find_vendored_mempalace, run_mempalace
from .types import RunResult, as_jsonable


CONFIG_FILE = "mempalace_config.json"
MANIFEST_FILE = "sync_manifest.jsonl"
CONTEXT_CACHE_FILE = "context_cache.jsonl"
PALACE_DIR = "mempalace-palace"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def memory_dir(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / CONFIG_DIR_NAME / "memory"


def exports_dir(project_root: str | Path) -> Path:
    return memory_dir(project_root) / "exports"


def config_path(project_root: str | Path) -> Path:
    return memory_dir(project_root) / CONFIG_FILE


def manifest_path(project_root: str | Path) -> Path:
    return memory_dir(project_root) / MANIFEST_FILE


def context_cache_path(project_root: str | Path) -> Path:
    return memory_dir(project_root) / CONTEXT_CACHE_FILE


def palace_path(project_root: str | Path) -> Path:
    return memory_dir(project_root) / PALACE_DIR


def ensure_memory_workspace(project_root: str | Path) -> Path:
    root = Path(project_root).resolve()
    mem_dir = memory_dir(root)
    mem_dir.mkdir(parents=True, exist_ok=True)
    exports_dir(root).mkdir(parents=True, exist_ok=True)
    manifest_path(root).touch(exist_ok=True)
    context_cache_path(root).touch(exist_ok=True)
    return mem_dir


def write_config(project_root: str | Path) -> Path:
    root = Path(project_root).resolve()
    ensure_memory_workspace(root)
    vendored = find_vendored_mempalace(root)
    data = {
        "engine": "mempalace",
        "project_root": str(root),
        "created_at": utc_now_iso(),
        "vendor_path": "vendor/mempalace" if vendored else None,
        "palace_path": str(palace_path(root)),
    }
    path = config_path(root)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def is_initialized(project_root: str | Path) -> bool:
    root = Path(project_root).resolve()
    return config_path(root).is_file()


def local_palace_args(project_root: str | Path, args: list[str]) -> list[str]:
    return ["--palace", str(palace_path(project_root)), *args]


def initialize_project(project_root: str | Path | None = None, timeout: int = 300) -> RunResult:
    root = find_project_root(project_root)
    write_config(root)
    args = local_palace_args(root, ["init", ".", "--yes", "--no-llm"])
    return run_mempalace(args, cwd=root, timeout=timeout)


def mine_path(
    target: str | Path,
    *,
    project_root: str | Path | None = None,
    timeout: int = 300,
    mode: str | None = None,
) -> RunResult:
    root = find_project_root(project_root)
    ensure_memory_workspace(root)
    args = local_palace_args(root, ["mine", str(target)])
    if mode:
        args.extend(["--mode", mode])
    return run_mempalace(args, cwd=root, timeout=timeout)


def mine_exports(project_root: str | Path | None = None, timeout: int = 300) -> RunResult:
    root = find_project_root(project_root)
    return mine_path(exports_dir(root), project_root=root, timeout=timeout)


def search_memory(
    query: str,
    *,
    project_root: str | Path | None = None,
    limit: int = 10,
    wing: str | None = None,
    timeout: int = 120,
) -> RunResult:
    root = find_project_root(project_root)
    args = local_palace_args(root, ["search", query, "--results", str(max(1, limit))])
    if wing:
        args.extend(["--wing", wing])
    return run_mempalace(args, cwd=root, timeout=timeout)


def wake_up(
    *,
    project_root: str | Path | None = None,
    query: str | None = None,
    max_chars: int = 6000,
    timeout: int = 120,
) -> RunResult:
    root = find_project_root(project_root)
    wake_result = run_mempalace(local_palace_args(root, ["wake-up"]), cwd=root, timeout=timeout)
    if query:
        search_result = search_memory(query, project_root=root, limit=5, timeout=timeout)
        combined_stdout = "\n\n".join(
            part for part in (
                wake_result.stdout.strip(),
                f"Relevant search for {query!r}:\n{search_result.stdout.strip()}" if search_result.stdout.strip() else "",
            )
            if part
        )
        wake_result = RunResult(
            argv=wake_result.argv,
            returncode=wake_result.returncode if wake_result.ok else search_result.returncode,
            stdout=combined_stdout,
            stderr="\n".join(part for part in (wake_result.stderr.strip(), search_result.stderr.strip()) if part),
            cwd=wake_result.cwd,
            source=wake_result.source,
            error=wake_result.error or search_result.error,
            timed_out=wake_result.timed_out or search_result.timed_out,
        )
    return _truncate_result(wake_result, max_chars=max_chars)


def status(project_root: str | Path | None = None, timeout: int = 120) -> RunResult:
    root = find_project_root(project_root)
    return run_mempalace(local_palace_args(root, ["status"]), cwd=root, timeout=timeout)


def append_manifest(project_root: str | Path, record: dict[str, object]) -> None:
    root = Path(project_root).resolve()
    ensure_memory_workspace(root)
    data = {"created_at": utc_now_iso(), **as_jsonable(record)}
    with manifest_path(root).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n")


def _truncate_result(result: RunResult, *, max_chars: int) -> RunResult:
    if max_chars <= 0 or len(result.stdout) <= max_chars:
        return result
    suffix = "\n\n[truncated]"
    text = result.stdout[: max(0, max_chars - len(suffix))].rstrip() + suffix
    return RunResult(
        argv=result.argv,
        returncode=result.returncode,
        stdout=text,
        stderr=result.stderr,
        cwd=result.cwd,
        source=result.source,
        error=result.error,
        timed_out=result.timed_out,
    )
