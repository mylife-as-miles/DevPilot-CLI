"""Shared reasoning-effort values and provider-specific mappings."""

from __future__ import annotations

REASONING_EFFORT_CHOICES = ("high", "medium", "low", "minimal", "none")
DEFAULT_REASONING_EFFORT = "high"

_GEMINI_THINKING_LEVEL = {
    "high": "high",
    "medium": "medium",
    "low": "low",
    "minimal": "minimal",
}


def gemini_thinking_level(reasoning_effort: str | None) -> str | None:
    """Map ``reasoning_effort`` to Gemini Interactions ``thinking_level``."""
    if reasoning_effort is None:
        return None
    effort = reasoning_effort.strip().lower()
    if not effort or effort == "none":
        return None
    return _GEMINI_THINKING_LEVEL.get(effort, effort)


def openai_reasoning_effort(reasoning_effort: str | None) -> str | None:
    """Map shared effort onto OpenAI Responses ``reasoning.effort``."""
    if reasoning_effort is None:
        return None
    effort = reasoning_effort.strip().lower()
    if not effort or effort == "none":
        return None
    if effort == "minimal":
        return "low"
    return effort
