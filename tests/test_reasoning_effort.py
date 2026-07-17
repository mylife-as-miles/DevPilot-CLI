"""Tests for shared reasoning-effort mappings."""

from __future__ import annotations

from devpilot.cli._constants import reasoning_effort_menu, uses_gemini_thinking_level
from devpilot.core.reasoning_effort import openai_reasoning_effort


def test_reasoning_menu_shows_gemini_hint():
    labels = dict(reasoning_effort_menu("gemini", "gemini-3-flash-preview"))
    assert "thinking_level" in labels["high"]
    assert "thinking_level" not in reasoning_effort_menu("anthropic")[0][1]


def test_uses_gemini_thinking_level_auto_with_gemini_model():
    assert uses_gemini_thinking_level("auto", "gemini-3-flash-preview") is True
    assert uses_gemini_thinking_level("auto", "gpt-5") is False


def test_openai_reasoning_effort_maps_minimal_to_low():
    assert openai_reasoning_effort("minimal") == "low"
    assert openai_reasoning_effort("high") == "high"
    assert openai_reasoning_effort("none") is None
