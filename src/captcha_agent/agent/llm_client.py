"""LLM provider abstraction and test fake."""

from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LLMTurn:
    tool_calls: list[ToolCall] = field(default_factory=list)
    text: str = ""
    raw_content: list[dict[str, Any]] = field(default_factory=list)


class LLMClient(Protocol):
    async def step(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMTurn:
        ...


class AnthropicClient:
    """Anthropic tool-use client configured from environment variables."""

    def __init__(self, model: str | None = None, max_tokens: int = 1024):
        self.model = model or os.getenv("LLM_MODEL", "claude-3-5-sonnet-latest")
        self.max_tokens = max_tokens
        self._client = None

    async def step(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMTurn:
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=messages[0]["content"] if messages and messages[0].get("role") == "system" else "",
            messages=[message for message in messages if message.get("role") != "system"],
            tools=tools,
        )
        calls: list[ToolCall] = []
        raw: list[dict[str, Any]] = []
        text_parts: list[str] = []
        for block in response.content:
            if block.type == "tool_use":
                arguments = block.input if isinstance(block.input, dict) else {}
                calls.append(ToolCall(id=block.id, name=block.name, arguments=arguments))
                raw.append({"type": "tool_use", "id": block.id, "name": block.name, "input": arguments})
            elif block.type == "text":
                text_parts.append(block.text)
                raw.append({"type": "text", "text": block.text})
        return LLMTurn(tool_calls=calls, text="\n".join(text_parts), raw_content=raw)


class FakeLLM:
    """Replay scripted turns and fail clearly if the script is exhausted."""

    def __init__(self, turns: list[LLMTurn | list[ToolCall] | ToolCall]):
        self.turns = [self._normalize(turn) for turn in turns]
        self.index = 0
        self.seen_messages: list[list[dict[str, Any]]] = []

    @staticmethod
    def _normalize(turn: LLMTurn | list[ToolCall] | ToolCall) -> LLMTurn:
        if isinstance(turn, LLMTurn):
            return turn
        if isinstance(turn, ToolCall):
            return LLMTurn(tool_calls=[turn])
        return LLMTurn(tool_calls=turn)

    async def step(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMTurn:
        self.seen_messages.append(messages)
        if self.index >= len(self.turns):
            return LLMTurn(text="script exhausted")
        turn = self.turns[self.index]
        self.index += 1
        return turn


class LocalMockLLM:
    """A no-network planner for the self-hosted fixture pages.

    It consumes the same tool results as an LLM turn, but makes the routing
    decision locally from ``detect_widget`` output. This is useful for demos,
    CI, and development without an Anthropic API key.
    """

    def __init__(self):
        self.stage = "detect"
        self.widget: str | None = None
        self.action_attempts = 0
        self._counter = 0

    def _call(self, name: str, **arguments: Any) -> LLMTurn:
        self._counter += 1
        return LLMTurn(
            tool_calls=[ToolCall(id=f"mock-{self._counter}", name=name, arguments=arguments)],
            text=f"Local mock decision: {name}",
            raw_content=[{"type": "tool_use", "id": f"mock-{self._counter}", "name": name, "input": arguments}],
        )

    @staticmethod
    def _last_tool_result(messages: list[dict[str, Any]]) -> dict[str, Any]:
        for message in reversed(messages):
            if message.get("role") != "user":
                continue
            for block in message.get("content", []):
                if block.get("type") == "tool_result":
                    try:
                        return json.loads(block.get("content", "{}"))
                    except (TypeError, json.JSONDecodeError):
                        return {}
        return {}

    async def step(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMTurn:
        result = self._last_tool_result(messages)
        if self.stage == "detect":
            self.stage = "route"
            return self._call("detect_widget")
        if self.stage == "route":
            self.widget = (result.get("data") or {}).get("widget")
            if self.widget == "checkbox":
                self.stage = "action"
                return self._call("click_checkbox")
            if self.widget == "slider":
                self.stage = "action"
                return self._call("solve_slider")
            self.stage = "verify"
            return self._call("verify_result")
        if self.stage == "action":
            if result.get("ok"):
                self.stage = "verify"
                return self._call("verify_result")
            self.action_attempts += 1
            if self.action_attempts < 3:
                return self._call("click_checkbox" if self.widget == "checkbox" else "solve_slider")
            self.stage = "verify"
            return self._call("verify_result")
        if self.stage == "verify":
            self.stage = "finish"
            return self._call("finish", status="success" if result.get("ok") else "failure", summary="local mock verification")
        return self._call("finish", status="failure", summary="local mock planner exhausted")
