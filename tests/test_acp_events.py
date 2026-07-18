from pathlib import Path

from devpilot.acp.events import AcpEventMapper, DevPilotEvent, normalize_event, read_appended_events


def test_read_appended_events_preserves_partial_final_line(tmp_path: Path) -> None:
    target = tmp_path / "events.jsonl"
    complete = b'{"ts":"2026-07-15T00:00:00Z","type":"idea.proposed","data":{"node_id":"1","hypothesis":"cache"}}\n'
    partial = b'{"type":"executor.start","data":{"node_id":"1"}'
    target.write_bytes(complete + partial)

    events, offset = read_appended_events(target, 0)

    assert [event.type for event in events] == ["idea.proposed"]
    assert events[0].data["node_id"] == "1"
    assert offset == len(complete)

    target.write_bytes(complete + partial + b"}\n")
    events, next_offset = read_appended_events(target, offset)
    assert [event.type for event in events] == ["executor.start"]
    assert next_offset == target.stat().st_size


def test_read_appended_events_skips_malformed_records(tmp_path: Path) -> None:
    target = tmp_path / "events.jsonl"
    target.write_text(
        "not-json\n"
        '{"type":"","data":{}}\n'
        '{"type":"session.start","data":{"task":"go"}}\n',
        encoding="utf-8",
    )

    events, offset = read_appended_events(target, 0)

    assert [event.type for event in events] == ["session.start"]
    assert offset == target.stat().st_size


def test_normalize_event_does_not_expose_mutable_runtime_objects() -> None:
    class RuntimeValue:
        def __str__(self) -> str:
            return "safe-display"

    event = normalize_event({
        "type": "tool.start",
        "ts": 123,
        "data": {
            "args": RuntimeValue(),
            "nested": (RuntimeValue(),),
            "api_key": "must-not-leak",
        },
    })

    assert event is not None
    assert event.timestamp is None
    assert event.data == {
        "args": "safe-display",
        "nested": ["safe-display"],
        "api_key": "[redacted]",
    }


def test_event_mapper_surfaces_hypotheses_executors_and_tools_as_standard_acp_updates() -> None:
    mapper = AcpEventMapper("session-1")

    proposed = mapper.updates(DevPilotEvent(
        type="idea.proposed",
        timestamp="2026-07-15T00:00:00Z",
        data={"node_id": "1", "hypothesis": "Cache dependency metadata"},
    ))
    executor = mapper.updates(DevPilotEvent(
        type="executor.start",
        timestamp=None,
        data={"node_id": "1", "branch": "devpilot/1"},
    ))
    tool_started = mapper.updates(DevPilotEvent(
        type="tool.start",
        timestamp=None,
        data={"name": "RunTests", "agent": "sub:1", "node_id": "1"},
    ))
    tool_ended = mapper.updates(DevPilotEvent(
        type="tool.end",
        timestamp=None,
        data={"name": "RunTests", "agent": "sub:1", "node_id": "1", "ok": True},
    ))

    assert proposed[0].session_update == "plan"
    assert proposed[0].entries[0].status == "pending"
    assert executor[0].entries[0].status == "in_progress"
    assert executor[1].session_update == "tool_call"
    assert executor[1].tool_call_id == "executor:session-1:1"
    assert tool_started[0].kind == "execute"
    assert tool_started[0].status == "in_progress"
    assert tool_ended[0].tool_call_id == tool_started[0].tool_call_id
    assert tool_ended[0].status == "completed"
    assert tool_ended[0].field_meta["devpilot"]["type"] == "tool.end"


def test_event_mapper_surfaces_reasoning_and_waiting_state() -> None:
    mapper = AcpEventMapper("session-2")

    thought = mapper.updates(DevPilotEvent(
        type="llm.thinking_delta",
        timestamp=None,
        data={"text": "Compare both approaches", "node_id": "1"},
    ))
    waiting = mapper.updates(DevPilotEvent(
        type="user.await",
        timestamp=None,
        data={"prompt": "Which dataset should I use?"},
    ))

    assert thought[0].session_update == "agent_thought_chunk"
    assert thought[0].content.text == "Compare both approaches"
    assert waiting[0].session_update == "agent_message_chunk"
    assert "waiting for input" in waiting[0].content.text
