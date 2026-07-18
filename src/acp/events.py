"""Read and normalize the durable DevPilot event stream for ACP clients."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from acp import (
    start_tool_call,
    text_block,
    update_agent_message,
    update_agent_thought,
    update_plan,
    update_tool_call,
)
from acp.schema import PlanEntry


@dataclass(frozen=True)
class DevPilotEvent:
    type: str
    timestamp: str | None
    data: dict[str, Any]

    def as_meta(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "timestamp": self.timestamp,
            "data": self.data,
        }


def read_appended_events(path: Path, offset: int) -> tuple[list[DevPilotEvent], int]:
    """Read complete JSONL records appended after *offset*.

    The file logger flushes each record, but a reader can still observe a partial
    final line. In that case the returned offset stays before that line so the
    next poll retries it instead of dropping an event.
    """
    try:
        with path.open("rb") as stream:
            stream.seek(offset)
            events: list[DevPilotEvent] = []
            committed_offset = offset
            while True:
                line_offset = stream.tell()
                raw = stream.readline()
                if not raw:
                    break
                if not raw.endswith(b"\n"):
                    committed_offset = line_offset
                    break
                committed_offset = stream.tell()
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                event = normalize_event(payload)
                if event is not None:
                    events.append(event)
            return events, committed_offset
    except OSError:
        return [], offset


def normalize_event(payload: Any) -> DevPilotEvent | None:
    """Return the immutable, JSON-safe face of one runtime event."""
    if not isinstance(payload, dict):
        return None
    event_type = payload.get("type")
    data = payload.get("data")
    timestamp = payload.get("ts")
    if not isinstance(event_type, str) or not event_type.strip():
        return None
    if not isinstance(data, dict):
        data = {}
    safe_data = _json_safe(data)
    if not isinstance(safe_data, dict):
        safe_data = {}
    return DevPilotEvent(
        type=event_type.strip(),
        timestamp=timestamp if isinstance(timestamp, str) else None,
        data=safe_data,
    )


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): "[redacted]" if _sensitive_key(str(key)) else _json_safe(item)
            for key, item in value.items()
        }
    return str(value)


def _sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(
        marker in normalized
        for marker in ("api_key", "apikey", "access_token", "refresh_token", "password", "secret", "authorization")
    )


class AcpEventMapper:
    """Translate DevPilot runtime events into standard ACP presentation updates."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._plan: dict[str, dict[str, str]] = {}
        self._tool_counter = 0
        self._active_tools: dict[tuple[str, str, str], list[str]] = {}

    def updates(self, event: DevPilotEvent) -> list[Any]:
        if event.type == "llm.thinking_delta":
            text = _string(event.data.get("text"))
            return [self._with_meta(update_agent_thought(text_block(text)), event)] if text else []

        if event.type in {"idea.proposed", "idea.completed", "idea.pruned", "idea.merged"}:
            self._update_plan_node(event)
            return [self._with_meta(update_plan(self._plan_entries()), event)]

        if event.type == "executor.start":
            return self._executor_started(event)
        if event.type == "executor.end":
            return self._executor_ended(event)
        if event.type == "tool.start":
            return self._tool_started(event)
        if event.type == "tool.end":
            return self._tool_ended(event)

        summary = format_event_summary(event)
        return [self._with_meta(update_agent_message(text_block(f"{summary}\n")), event)] if summary else []

    def _update_plan_node(self, event: DevPilotEvent) -> None:
        node_id = _string(event.data.get("node_id")) or "unknown"
        existing = self._plan.get(node_id, {})
        hypothesis = _string(event.data.get("hypothesis")) or _string(event.data.get("idea"))
        content = hypothesis or existing.get("content") or f"Hypothesis {node_id}"
        if event.type == "idea.proposed":
            status = "pending"
        elif event.type in {"idea.completed", "idea.merged", "idea.pruned"}:
            status = "completed"
        else:
            status = existing.get("status", "pending")
        self._plan[node_id] = {"content": f"[{node_id}] {content}", "status": status}

    def _plan_entries(self) -> list[PlanEntry]:
        return [
            PlanEntry(content=item["content"], priority="medium", status=item["status"])
            for item in self._plan.values()
        ]

    def _executor_started(self, event: DevPilotEvent) -> list[Any]:
        node_id = _string(event.data.get("node_id")) or "unknown"
        if node_id in self._plan:
            self._plan[node_id]["status"] = "in_progress"
        tool_call_id = f"executor:{self.session_id}:{node_id}"
        update = start_tool_call(
            tool_call_id,
            f"Executor {node_id}",
            kind="execute",
            status="in_progress",
            raw_input=event.data,
        )
        updates: list[Any] = []
        if self._plan:
            updates.append(self._with_meta(update_plan(self._plan_entries()), event))
        updates.append(self._with_meta(update, event))
        return updates

    def _executor_ended(self, event: DevPilotEvent) -> list[Any]:
        node_id = _string(event.data.get("node_id")) or "unknown"
        if node_id in self._plan:
            self._plan[node_id]["status"] = "completed"
        update = update_tool_call(
            f"executor:{self.session_id}:{node_id}",
            title=f"Executor {node_id}",
            kind="execute",
            status="completed",
            raw_output=event.data,
        )
        updates: list[Any] = []
        if self._plan:
            updates.append(self._with_meta(update_plan(self._plan_entries()), event))
        updates.append(self._with_meta(update, event))
        return updates

    def _tool_started(self, event: DevPilotEvent) -> list[Any]:
        name = _string(event.data.get("name")) or "Tool"
        key = self._tool_key(event, name)
        self._tool_counter += 1
        tool_call_id = f"tool:{self.session_id}:{self._tool_counter}"
        self._active_tools.setdefault(key, []).append(tool_call_id)
        update = start_tool_call(
            tool_call_id,
            name,
            kind=_tool_kind(name),
            status="in_progress",
            raw_input=event.data,
        )
        return [self._with_meta(update, event)]

    def _tool_ended(self, event: DevPilotEvent) -> list[Any]:
        name = _string(event.data.get("name")) or "Tool"
        key = self._tool_key(event, name)
        active = self._active_tools.get(key, [])
        tool_call_id = active.pop(0) if active else f"tool:{self.session_id}:unmatched:{name}"
        ok = event.data.get("ok") is not False
        update = update_tool_call(
            tool_call_id,
            title=name,
            kind=_tool_kind(name),
            status="completed" if ok else "failed",
            raw_output=event.data,
        )
        return [self._with_meta(update, event)]

    @staticmethod
    def _tool_key(event: DevPilotEvent, name: str) -> tuple[str, str, str]:
        return (
            _string(event.data.get("agent")),
            _string(event.data.get("node_id")),
            name,
        )

    @staticmethod
    def _with_meta(update: Any, event: DevPilotEvent) -> Any:
        return update.model_copy(update={"field_meta": {"devpilot": event.as_meta()}})


def format_event_summary(event: DevPilotEvent) -> str:
    data = event.data
    if event.type == "session.start":
        return f"Research run started: {_string(data.get('task')) or 'DevPilot task'}"
    if event.type == "session.end":
        return f"Research run ended ({_string(data.get('exit_reason')) or 'complete'})."
    if event.type == "cycle.start":
        return f"Cycle {data.get('cycle_num', '?')} of {data.get('total_cycles', '?')} started."
    if event.type == "cycle.end":
        return f"Cycle {data.get('cycle_num', '?')} completed."
    if event.type == "cycle.phase":
        return f"Coordinator phase: {_string(data.get('phase')) or 'working'}"
    if event.type == "user.await":
        return f"DevPilot is waiting for input: {_string(data.get('prompt'))}"
    if event.type == "llm.error":
        return f"Provider error: {_string(data.get('error')) or 'unknown error'}"
    if event.type == "session.checkpoint":
        return f"Checkpoint saved for cycle {data.get('cycle', '?')}."
    return ""


def _string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _tool_kind(name: str) -> str:
    lowered = name.lower()
    if any(token in lowered for token in ("read", "view", "open")):
        return "read"
    if any(token in lowered for token in ("write", "edit", "patch")):
        return "edit"
    if "delete" in lowered or "remove" in lowered:
        return "delete"
    if "search" in lowered or "grep" in lowered:
        return "search"
    if any(token in lowered for token in ("fetch", "reach", "web")):
        return "fetch"
    if any(token in lowered for token in ("bash", "shell", "run", "test", "exec")):
        return "execute"
    return "other"
