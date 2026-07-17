"""Gemini Interactions API provider with reasoning and function calling."""

# pylint: disable=broad-exception-caught

from __future__ import annotations

import copy
import json
import logging
import os
from typing import Any

import tiktoken

from .base import (
    ContentBlock,
    LLMProvider,
    LLMResponse,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    Usage,
    make_tool_use_id,
)

log = logging.getLogger(__name__)

_NATIVE_STEP_TYPES = frozenset({
    "user_input",
    "model_output",
    "thought",
    "function_call",
    "function_result",
})

from ..reasoning_effort import gemini_thinking_level


def _gemini_api_key(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _normalize_model(model: str) -> str:
    bare = (model or "").strip()
    if bare.startswith("models/"):
        return bare[len("models/"):]
    return bare


class GeminiInteractionsProvider(LLMProvider):
    """LLM provider backed by the Gemini Interactions API."""

    def __init__(
        self,
        model: str = "gemini-3-flash-preview",
        api_key: str | None = None,
        base_url: str | None = None,
        max_retries: int = 3,
        timeout: float = 300.0,
        reasoning_effort: str | None = "high",
    ):
        from google import genai

        self.model = _normalize_model(model)
        self.base_url = base_url
        self.timeout = timeout
        self.reasoning_effort = reasoning_effort
        client_kwargs: dict[str, Any] = {
            "api_key": _gemini_api_key(api_key),
            "http_options": {"timeout": int(timeout * 1000)},
        }
        if base_url:
            client_kwargs["http_options"] = {
                "base_url": base_url.rstrip("/"),
                "timeout": int(timeout * 1000),
            }
        self._client = genai.Client(**client_kwargs)
        try:
            self._enc = tiktoken.encoding_for_model("gpt-4")
        except (KeyError, ValueError):
            self._enc = tiktoken.get_encoding("cl100k_base")
        # Server-side interaction chain (``store=True`` + ``previous_interaction_id``).
        # Stateless full-history replay is rejected by Gemini on tool follow-ups.
        self._last_interaction_id: str | None = None
        self._messages_at_last_create: int = 0

    def _reset_chain(self) -> None:
        self._last_interaction_id = None
        self._messages_at_last_create = 0

    async def create(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 16384,
    ) -> LLMResponse:
        params = self._build_request_params(
            system=system,
            messages=messages,
            tools=tools,
            max_tokens=max_tokens,
        )
        raw = await self._client.aio.interactions.create(**params)
        interaction_id = getattr(raw, "id", None)
        if interaction_id:
            self._last_interaction_id = str(interaction_id)
            self._messages_at_last_create = len(messages)
        return self._parse_response(raw)

    def count_tokens(self, text: str) -> int:
        return len(self._enc.encode(text))

    def _build_request_params(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
    ) -> dict[str, Any]:
        generation_config: dict[str, Any] = {"max_output_tokens": max_tokens}
        thinking_level = self._thinking_level()
        if thinking_level is not None:
            generation_config["thinking_level"] = thinking_level

        if (
            self._last_interaction_id
            and len(messages) < self._messages_at_last_create
        ):
            log.info("gemini interaction chain reset (messages shrank)")
            self._reset_chain()

        use_chain = bool(self._last_interaction_id)
        params: dict[str, Any] = {
            "model": self.model,
            "input": self._resolve_input(messages, use_chain=use_chain),
            "store": True,
            "generation_config": generation_config,
        }
        if use_chain:
            params["previous_interaction_id"] = self._last_interaction_id
        else:
            params["system_instruction"] = system
        if tools:
            params["tools"] = self._convert_tools(tools)
        return params

    def _resolve_input(
        self,
        messages: list[dict[str, Any]],
        *,
        use_chain: bool,
    ) -> str | list[dict[str, Any]]:
        """Build ``input`` for the Interactions API.

        First turn sends the opening user message. Follow-ups send only the
        latest user delta (tool results or a new user utterance) and rely on
        ``previous_interaction_id`` for server-side history.
        """
        if not messages:
            raise ValueError("messages must not be empty")

        if use_chain:
            last = messages[-1]
            if last.get("role") != "user":
                raise ValueError("chained follow-up must end with a user message")
            steps = self._user_message_to_steps(last.get("content", ""))
            return self._finalize_replay_steps(steps)

        first = messages[0]
        if first.get("role") != "user":
            raise ValueError("conversation must start with a user message")
        steps = self._user_message_to_steps(first.get("content", ""))
        if len(steps) == 1 and steps[0].get("type") == "user_input":
            content = steps[0].get("content")
            if (
                isinstance(content, list)
                and len(content) == 1
                and content[0].get("type") == "text"
            ):
                return str(content[0].get("text", ""))
        return steps

    def _thinking_level(self) -> str | None:
        return gemini_thinking_level(self.reasoning_effort)

    @staticmethod
    def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            }
            for tool in tools
        ]

    def _convert_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        steps: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                steps.extend(self._user_message_to_steps(content))
            elif role == "assistant":
                steps.extend(self._assistant_message_to_steps(content))
        return self._finalize_replay_steps(steps)

    @classmethod
    def _finalize_replay_steps(cls, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize history for stateless Interactions replay (``store=False``).

        Gemini rejects some replayed payloads on follow-up turns — notably
        ``function_result`` steps missing the matching tool ``name``, and
        ``thought`` steps that cannot be faithfully re-sent without server state.
        """
        call_names: dict[str, str] = {}
        for step in steps:
            if step.get("type") == "function_call":
                call_id = str(step.get("id") or "")
                tool_name = str(step.get("name") or "")
                if call_id and tool_name:
                    call_names[call_id] = tool_name

        finalized: list[dict[str, Any]] = []
        for step in steps:
            step_type = step.get("type")
            if step_type == "thought":
                # Display-only in our ReAct loop; replay breaks stateless requests.
                continue
            if step_type == "function_result":
                step = copy.deepcopy(step)
                call_id = str(step.get("call_id") or "")
                if not step.get("name") and call_id in call_names:
                    step["name"] = call_names[call_id]
                if not step.get("name"):
                    log.warning("dropping function_result without tool name for call_id=%s", call_id)
                    continue
            finalized.append(step)
        return finalized

    def _user_message_to_steps(self, content: Any) -> list[dict[str, Any]]:
        if isinstance(content, str):
            text = content.strip()
            if not text:
                return []
            return [{"type": "user_input", "content": [{"type": "text", "text": text}]}]

        if not isinstance(content, list):
            return [{"type": "user_input", "content": [{"type": "text", "text": str(content)}]}]

        steps: list[dict[str, Any]] = []
        text_parts: list[str] = []

        def flush_text() -> None:
            if text_parts:
                steps.append({
                    "type": "user_input",
                    "content": [{"type": "text", "text": "\n".join(text_parts)}],
                })
                text_parts.clear()

        for block in content:
            if not isinstance(block, dict):
                flush_text()
                text_parts.append(str(block))
                continue
            block_type = block.get("type")
            if block_type == "text":
                text = str(block.get("text", "")).strip()
                if text:
                    text_parts.append(text)
            elif block_type == "tool_result":
                flush_text()
                steps.append({
                    "type": "function_result",
                    "call_id": block.get("tool_use_id", ""),
                    "name": block.get("name", ""),
                    "result": block.get("content", ""),
                    **({"is_error": True} if block.get("is_error") else {}),
                })
            elif block_type == "function_result":
                flush_text()
                steps.append(copy.deepcopy(block))
        flush_text()
        return steps

    def _assistant_message_to_steps(self, content: Any) -> list[dict[str, Any]]:
        if isinstance(content, str):
            text = content.strip()
            if not text:
                return []
            return [{"type": "model_output", "content": [{"type": "text", "text": text}]}]

        if not isinstance(content, list):
            return []

        steps: list[dict[str, Any]] = []
        text_parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                text_parts.append(str(block))
                continue
            block_type = block.get("type")
            if block_type in _NATIVE_STEP_TYPES:
                steps.append(copy.deepcopy(block))
            elif block_type == "text":
                text = str(block.get("text", "")).strip()
                if text:
                    text_parts.append(text)
            elif block_type == "thinking":
                signature = block.get("signature")
                if signature:
                    step: dict[str, Any] = {"type": "thought", "signature": signature}
                    summary = block.get("summary")
                    if isinstance(summary, list):
                        step["summary"] = copy.deepcopy(summary)
                    else:
                        text = block.get("thinking") or block.get("text") or ""
                        if text:
                            step["summary"] = [{"type": "text", "text": str(text)}]
                    steps.append(step)
            elif block_type == "tool_use":
                steps.append({
                    "type": "function_call",
                    "id": block.get("id") or make_tool_use_id(),
                    "name": block.get("name", ""),
                    "arguments": block.get("input", {}),
                })
        if text_parts:
            steps.append({
                "type": "model_output",
                "content": [{"type": "text", "text": "\n".join(text_parts)}],
            })
        return steps

    def _parse_response(self, raw: Any) -> LLMResponse:
        steps = [
            step for step in self._to_python(getattr(raw, "steps", None) or [])
            if isinstance(step, dict)
        ]

        content: list[ContentBlock] = []
        raw_content: list[dict[str, Any]] = []
        tool_calls: list[ToolUseBlock] = []

        for step in steps:
            step_type = step.get("type")
            raw_content.append(copy.deepcopy(step))
            if step_type == "thought":
                text = self._thought_text(step)
                if text:
                    content.append(ThinkingBlock(text=text, signature=str(step.get("signature", ""))))
            elif step_type == "model_output":
                text = self._content_text(step.get("content"))
                if text:
                    content.append(TextBlock(text=text))
            elif step_type == "function_call":
                call_id = step.get("id") or make_tool_use_id()
                tool_calls.append(ToolUseBlock(
                    id=call_id,
                    name=step.get("name", ""),
                    input=self._parse_arguments(step.get("arguments")),
                ))

        if tool_calls:
            content.extend(tool_calls)

        if not any(isinstance(b, TextBlock) for b in content):
            output_text = getattr(raw, "output_text", None) or ""
            if output_text:
                content.insert(0, TextBlock(text=str(output_text)))
                if not any(s.get("type") == "model_output" for s in raw_content):
                    raw_content.append({
                        "type": "model_output",
                        "content": [{"type": "text", "text": str(output_text)}],
                    })

        usage = Usage()
        raw_usage = getattr(raw, "usage", None)
        if raw_usage is not None:
            usage.input_tokens = int(getattr(raw_usage, "total_input_tokens", 0) or 0)
            usage.output_tokens = int(getattr(raw_usage, "total_output_tokens", 0) or 0)
            usage.cache_read_tokens = int(getattr(raw_usage, "total_cached_tokens", 0) or 0)

        status = getattr(raw, "status", None)
        stop_reason = "tool_use" if tool_calls or status == "requires_action" else "end_turn"
        if status == "incomplete":
            stop_reason = "max_tokens"

        return LLMResponse(
            content=content,
            stop_reason=stop_reason,
            usage=usage,
            model=getattr(raw, "model", None) or self.model,
            raw_content=raw_content,
        )

    @classmethod
    def _thought_text(cls, step: dict[str, Any]) -> str:
        summary = step.get("summary")
        if isinstance(summary, list):
            return cls._content_text(summary)
        if isinstance(summary, str):
            return summary.strip()
        return ""

    @classmethod
    def _content_text(cls, content: Any) -> str:
        if isinstance(content, str):
            return content.strip()
        if not isinstance(content, list):
            return ""
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = str(block.get("text", "")).strip()
                if text:
                    parts.append(text)
        return "\n".join(parts).strip()

    @staticmethod
    def _parse_arguments(arguments: Any) -> dict[str, Any]:
        if isinstance(arguments, dict):
            return arguments
        if not arguments:
            return {}
        if not isinstance(arguments, str):
            return {}
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @classmethod
    def _to_python(cls, value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            return [cls._to_python(item) for item in value]
        if isinstance(value, tuple):
            return [cls._to_python(item) for item in value]
        if isinstance(value, dict):
            return {k: cls._to_python(v) for k, v in value.items()}

        for method_name in ("model_dump", "to_dict", "dict"):
            method = getattr(value, method_name, None)
            if callable(method):
                try:
                    return cls._to_python(method(exclude_none=True))
                except TypeError:
                    return cls._to_python(method())

        if hasattr(value, "__dict__"):
            return {
                key: cls._to_python(val)
                for key, val in vars(value).items()
                if not key.startswith("_")
            }

        return value
