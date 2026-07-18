"""Types for DevPilot's optional Headroom compression bridge."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class HeadroomInvocation:
    argv: list[str]
    cwd: Path
    env: dict[str, str] | None
    source: str


@dataclass(frozen=True)
class RunResult:
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
class CompressionArtifact:
    path: Path | None
    content: str = ""
    source_count: int = 0
    message: str = ""
    warnings: list[str] = field(default_factory=list)
