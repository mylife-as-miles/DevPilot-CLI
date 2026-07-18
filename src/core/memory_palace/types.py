"""Typed records for the optional MemPalace integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MemPalaceInvocation:
    """Resolved MemPalace command invocation."""

    argv: list[str]
    cwd: Path
    env: dict[str, str] | None
    source: str


@dataclass(frozen=True)
class RunResult:
    """Structured subprocess result returned by the MemPalace bridge."""

    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    cwd: str
    source: str
    error: str | None = None
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and self.error is None and not self.timed_out


@dataclass(frozen=True)
class SyncExportResult:
    """Summary of DevPilot artifacts exported for MemPalace mining."""

    files: list[Path] = field(default_factory=list)
    records: int = 0
    message: str = ""

    @property
    def has_exports(self) -> bool:
        return bool(self.files)


def json_safe_path(path: Path) -> str:
    return str(path).replace("\\", "/")


def as_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return json_safe_path(value)
    if isinstance(value, dict):
        return {str(k): as_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [as_jsonable(v) for v in value]
    return value
