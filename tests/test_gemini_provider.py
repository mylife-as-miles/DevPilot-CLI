"""Tests for the Gemini Interactions API provider."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from devpilot.cli._autodetect import resolve_auto_provider
from devpilot.cli._constants import canonical_provider, default_model_for_provider
from devpilot.core import resolve_backend
from devpilot.core.llm.gemini import GeminiInteractionsProvider, _normalize_model
from devpilot.core.reasoning_effort import gemini_thinking_level


def test_resolve_backend_recognizes_gemini():
    assert resolve_backend("gemini", None, "gemini-3-flash-preview", None) == "gemini"
    assert resolve_backend("google", None, "gemini-2.5-flash", None) == "gemini"


def test_auto_provider_routes_gemini_models():
    provider, reason = resolve_auto_provider(
        model="gemini-3-flash-preview",
        base_url=None,
        api_key="test",
    )
    assert provider == "gemini"
    assert "Interactions API" in reason


def test_canonical_and_default_model():
    assert canonical_provider("gemini") == "gemini"
    assert canonical_provider("google") == "gemini"
    assert default_model_for_provider("gemini") == "gemini-3-flash-preview"


def test_normalize_model_strips_models_prefix():
    assert _normalize_model("models/gemini-3-flash-preview") == "gemini-3-flash-preview"
    assert _normalize_model("gemini-3-flash-preview") == "gemini-3-flash-preview"


def test_convert_messages_roundtrip_steps():
    provider = GeminiInteractionsProvider(model="gemini-3-flash-preview", api_key="test")
    steps = provider._convert_messages([
        {"role": "user", "content": "hello"},
        {
            "role": "assistant",
            "content": [
                {"type": "function_call", "id": "call-1", "name": "read_file", "arguments": {"path": "a.py"}},
                {"type": "model_output", "content": [{"type": "text", "text": "checking file"}]},
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call-1",
                    "name": "read_file",
                    "content": "print('hi')",
                },
            ],
        },
    ])
    assert steps[0]["type"] == "user_input"
    assert steps[1]["type"] == "function_call"
    assert steps[2]["type"] == "model_output"
    assert steps[3]["type"] == "function_result"
    assert steps[3]["call_id"] == "call-1"
    assert steps[3]["name"] == "read_file"


def test_finalize_replay_steps_fills_missing_tool_name():
    steps = GeminiInteractionsProvider._finalize_replay_steps([
        {"type": "function_call", "id": "call-9", "name": "glob", "arguments": {"pattern": "*.py"}},
        {"type": "function_result", "call_id": "call-9", "result": "found 3 files"},
    ])
    assert len(steps) == 2
    assert steps[1]["name"] == "glob"


def test_finalize_replay_steps_drops_thoughts():
    steps = GeminiInteractionsProvider._finalize_replay_steps([
        {"type": "thought", "signature": "sig", "summary": [{"type": "text", "text": "hmm"}]},
        {"type": "model_output", "content": [{"type": "text", "text": "ok"}]},
    ])
    assert len(steps) == 1
    assert steps[0]["type"] == "model_output"


def test_parse_response_maps_tool_calls_and_thoughts():
    provider = GeminiInteractionsProvider(model="gemini-3-flash-preview", api_key="test")
    raw = SimpleNamespace(
        model="gemini-3-flash-preview",
        status="requires_action",
        output_text="",
        usage=SimpleNamespace(
            total_input_tokens=100,
            total_output_tokens=40,
            total_cached_tokens=10,
        ),
        steps=[
            {
                "type": "thought",
                "signature": "sig-1",
                "summary": [{"type": "text", "text": "planning"}],
            },
            {
                "type": "function_call",
                "id": "call-2",
                "name": "bash",
                "arguments": {"command": "ls"},
            },
        ],
    )
    response = provider._parse_response(raw)
    assert response.stop_reason == "tool_use"
    assert response.usage.input_tokens == 100
    assert response.usage.cache_read_tokens == 10
    tool_calls = response.get_tool_calls()
    assert len(tool_calls) == 1
    assert tool_calls[0].name == "bash"
    assert any(block.type == "thinking" for block in response.content)


def test_gemini_thinking_level_mapping():
    assert gemini_thinking_level("high") == "high"
    assert gemini_thinking_level("medium") == "medium"
    assert gemini_thinking_level("low") == "low"
    assert gemini_thinking_level("minimal") == "minimal"
    assert gemini_thinking_level("none") is None
    assert gemini_thinking_level(None) is None


def test_create_uses_interactions_api(monkeypatch):
    provider = GeminiInteractionsProvider(model="models/gemini-3-flash-preview", api_key="test")
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            model="gemini-3-flash-preview",
            status="completed",
            output_text="done",
            usage=SimpleNamespace(
                total_input_tokens=1,
                total_output_tokens=2,
                total_cached_tokens=0,
            ),
            steps=[{
                "type": "model_output",
                "content": [{"type": "text", "text": "done"}],
            }],
        )

    provider._client.aio.interactions.create = fake_create  # type: ignore[method-assign]

    response = asyncio.run(provider.create(
        system="You are helpful.",
        messages=[{"role": "user", "content": "hi"}],
        tools=[{
            "name": "bash",
            "description": "run shell",
            "input_schema": {"type": "object", "properties": {}},
        }],
        max_tokens=8192,
    ))

    assert captured["model"] == "gemini-3-flash-preview"
    assert captured["system_instruction"] == "You are helpful."
    assert captured["store"] is True
    assert "previous_interaction_id" not in captured
    assert captured["generation_config"]["max_output_tokens"] == 8192
    assert captured["generation_config"]["thinking_level"] == "high"
    assert captured["tools"][0]["name"] == "bash"
    assert response.get_text() == "done"


def test_create_respects_low_reasoning_effort(monkeypatch):
    provider = GeminiInteractionsProvider(
        model="gemini-3-flash-preview",
        api_key="test",
        reasoning_effort="low",
    )
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            model="gemini-3-flash-preview",
            status="completed",
            output_text="ok",
            usage=SimpleNamespace(
                total_input_tokens=1,
                total_output_tokens=1,
                total_cached_tokens=0,
            ),
            steps=[],
        )

    provider._client.aio.interactions.create = fake_create  # type: ignore[method-assign]
    asyncio.run(provider.create(system="sys", messages=[{"role": "user", "content": "hi"}]))
    assert captured["generation_config"]["thinking_level"] == "low"


def test_create_omits_thinking_level_when_none(monkeypatch):
    provider = GeminiInteractionsProvider(
        model="gemini-3-flash-preview",
        api_key="test",
        reasoning_effort="none",
    )
    captured: dict = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            model="gemini-3-flash-preview",
            status="completed",
            output_text="ok",
            usage=SimpleNamespace(
                total_input_tokens=1,
                total_output_tokens=1,
                total_cached_tokens=0,
            ),
            steps=[],
        )

    provider._client.aio.interactions.create = fake_create  # type: ignore[method-assign]
    asyncio.run(provider.create(system="sys", messages=[{"role": "user", "content": "hi"}]))
    assert "thinking_level" not in captured["generation_config"]


def test_create_chains_tool_results_with_previous_interaction_id(monkeypatch):
    provider = GeminiInteractionsProvider(model="gemini-3-flash-preview", api_key="test")
    calls: list[dict] = []

    async def fake_create(**kwargs):
        calls.append(dict(kwargs))
        status = "requires_action" if len(calls) == 1 else "completed"
        steps = (
            [{
                "type": "function_call",
                "id": "call-1",
                "name": "glob",
                "arguments": {"pattern": "*.py"},
            }]
            if len(calls) == 1
            else [{
                "type": "model_output",
                "content": [{"type": "text", "text": "found files"}],
            }]
        )
        return SimpleNamespace(
            id=f"interaction-{len(calls)}",
            model="gemini-3-flash-preview",
            status=status,
            output_text="found files" if len(calls) > 1 else "",
            usage=SimpleNamespace(
                total_input_tokens=1,
                total_output_tokens=1,
                total_cached_tokens=0,
            ),
            steps=steps,
        )

    provider._client.aio.interactions.create = fake_create  # type: ignore[method-assign]

    first = asyncio.run(provider.create(
        system="sys",
        messages=[{"role": "user", "content": "list files"}],
        tools=[{
            "name": "glob",
            "description": "glob",
            "input_schema": {"type": "object", "properties": {}},
        }],
    ))
    assert first.stop_reason == "tool_use"
    assert calls[0]["store"] is True
    assert calls[0]["system_instruction"] == "sys"
    assert calls[0]["input"] == "list files"
    assert "previous_interaction_id" not in calls[0]

    second = asyncio.run(provider.create(
        system="sys",
        messages=[
            {"role": "user", "content": "list files"},
            {"role": "assistant", "content": first.raw_content},
            {
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "call-1",
                    "name": "glob",
                    "content": "a.py",
                }],
            },
        ],
        tools=[{
            "name": "glob",
            "description": "glob",
            "input_schema": {"type": "object", "properties": {}},
        }],
    ))
    assert second.stop_reason == "end_turn"
    assert calls[1]["previous_interaction_id"] == "interaction-1"
    assert calls[1]["store"] is True
    assert "system_instruction" not in calls[1]
    assert calls[1]["input"] == [{
        "type": "function_result",
        "call_id": "call-1",
        "name": "glob",
        "result": "a.py",
    }]
