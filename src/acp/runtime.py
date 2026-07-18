"""Pure runtime/session helpers for the ACP adapter."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, NamedTuple


class DevPilotMode(NamedTuple):
    id: str
    name: str
    description: str


DEVPILOT_MODES: tuple[DevPilotMode, ...] = (
    DevPilotMode("research", "Research", "Run the full Coordinator-driven hypothesis workflow."),
    DevPilotMode("plan", "Plan", "Inspect the project and produce a plan without intentional code changes."),
    DevPilotMode("execute", "Execute", "Perform one narrow implementation experiment."),
    DevPilotMode("review", "Review", "Review code, diffs, branches, or issue context."),
    DevPilotMode("audit", "Audit", "Run an operational and code-quality audit."),
    DevPilotMode("memory", "Memory", "Search DevPilot memory and prior sessions."),
)

MODE_IDS = frozenset(mode.id for mode in DEVPILOT_MODES)

_MODE_PROMPT_PREFIXES = {
    "plan": "Plan-only mode: inspect and report a concrete plan. Do not modify files or Git state.\n\n",
    "execute": "Execute one narrow implementation task and stop after the first experiment.\n\n",
    "review": "Review mode: inspect the requested code or changes and report findings. Do not modify files.\n\n",
    "audit": "Audit mode: run the relevant DevPilot audit workflow and report its findings.\n\n",
    "memory": "Memory mode: search existing DevPilot memory and prior sessions. Do not modify files.\n\n",
}


@dataclass
class AcpSession:
    session_id: str
    cwd: Path
    mode: str = "research"
    model: str | None = None
    reasoning_effort: str | None = None
    run_name: str = ""
    has_started: bool = False
    title: str | None = None
    updated_at: str | None = None
    process: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.cwd = self.cwd.expanduser().resolve()
        if self.mode not in MODE_IDS:
            raise ValueError(f"unsupported DevPilot mode: {self.mode}")
        if not self.run_name:
            self.run_name = f"acp-{self.session_id}"


def extract_prompt_text(blocks: Iterable[Any]) -> str:
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, dict):
            block_type = block.get("type")
            text = block.get("text")
        else:
            block_type = getattr(block, "type", None)
            text = getattr(block, "text", None)
        if block_type == "text" and isinstance(text, str) and text.strip():
            parts.append(text.strip())
    if not parts:
        raise ValueError("ACP prompt must contain at least one non-empty text block")
    return "\n\n".join(parts)


def build_run_invocation(session: AcpSession, prompt: str) -> tuple[str, ...]:
    if not session.cwd.is_dir():
        raise ValueError(f"project directory is not accessible: {session.cwd}")
    task = f"{_MODE_PROMPT_PREFIXES.get(session.mode, '')}{prompt}".strip()
    args = [
        sys.executable,
        "-m",
        "devpilot.cli.app",
        "run",
        task,
        "--yes",
        "--yes-cwd",
        str(session.cwd),
        "--run-name",
        session.run_name,
        "--no-dashboard-input",
        "--no-webui",
        "--no-followup",
        "--interaction-mode",
        "auto",
    ]
    if session.mode == "execute":
        args.extend(("--max-cycles", "1"))
    if session.has_started:
        args.append("--resume")
    return tuple(args)
