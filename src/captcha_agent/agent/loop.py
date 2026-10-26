"""Observe-decide-act-check-stop agent loop."""

from __future__ import annotations

import asyncio
import base64
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..models import ToolResult
from ..tools import TOOL_REGISTRY, RunContext, ToolDefinition
from ..tools.observe import tool as observe
from .llm_client import LLMClient, LLMTurn
from .prompts import SYSTEM_PROMPT


@dataclass
class AgentResult:
    success: bool = False
    finished: bool = False
    steps: int = 0
    attempted_tool: str | None = None
    reason: str | None = None
    tool_errors: int = 0
    observations: list[dict[str, Any]] = field(default_factory=list)


def _image_message(path: str | None) -> dict[str, Any] | None:
    if not path or not Path(path).exists():
        return None
    data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}


async def _observe(ctx: RunContext, messages: list[dict[str, Any]], result: AgentResult) -> ToolResult:
    observation = await observe(ctx)
    result.observations.append(observation.data or {})
    content: list[dict[str, Any]] = [{"type": "text", "text": json.dumps(observation.data or {}, default=str)}]
    image = _image_message(observation.screenshot_path)
    if image:
        content.append(image)
    messages.append({"role": "user", "content": content})
    ctx.evidence.log_event("agent_observation", {"data": observation.data, "screenshot_path": observation.screenshot_path})
    return observation


async def run(
    ctx: RunContext,
    llm: LLMClient,
    max_steps: int | None = None,
    wall_clock_timeout_s: float = 60.0,
    max_tool_errors: int = 3,
) -> AgentResult:
    """Run a guarded agent loop using the shared tool registry."""
    result = AgentResult()
    limit = max_steps or ctx.config.settings.max_steps
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    tools = [{"name": item.name, "description": item.description, "input_schema": item.json_schema} for item in TOOL_REGISTRY.values()]
    started = time.monotonic()

    await _observe(ctx, messages, result)
    while result.steps < limit and time.monotonic() - started < wall_clock_timeout_s:
        remaining = wall_clock_timeout_s - (time.monotonic() - started)
        try:
            turn: LLMTurn = await asyncio.wait_for(llm.step(messages, tools), timeout=max(0.01, remaining))
        except asyncio.TimeoutError:
            result.reason = "agent wall-clock timeout"
            break
        messages.append({"role": "assistant", "content": turn.raw_content or [{"type": "text", "text": turn.text}]})
        ctx.evidence.log_event("agent_llm_turn", {"text": turn.text, "tool_calls": [call.__dict__ for call in turn.tool_calls]})
        if not turn.tool_calls:
            result.tool_errors += 1
            result.reason = "LLM returned no tool call"
            if result.tool_errors >= max_tool_errors:
                break
            await _observe(ctx, messages, result)
            continue

        for call in turn.tool_calls:
            result.steps += 1
            definition: ToolDefinition | None = TOOL_REGISTRY.get(call.name)
            if definition is None:
                tool_result = ToolResult(ok=False, error=f"Unknown tool: {call.name}")
            else:
                try:
                    validated = definition.args_model.model_validate(call.arguments)
                    tool_result = await definition.handler(ctx, **validated.model_dump())
                except Exception as exc:
                    tool_result = ToolResult(ok=False, error=f"Invalid tool call: {exc}")
            ctx.evidence.log_event("agent_tool_call", {"id": call.id, "name": call.name, "arguments": call.arguments, "rationale": turn.text[:240], "result": tool_result.model_dump()})
            messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": call.id, "content": json.dumps(tool_result.model_dump(), default=str)}]})
            if not tool_result.ok:
                result.tool_errors += 1
                result.reason = tool_result.error
                if result.tool_errors >= max_tool_errors:
                    break
            else:
                result.tool_errors = 0
            if call.name in {"click_checkbox", "solve_slider"}:
                result.attempted_tool = call.name
            if call.name == "verify_result":
                result.success = tool_result.ok
            if call.name == "finish":
                result.finished = True
                # Never trust finish's payload; success only comes from verify_result.
                if not result.success:
                    result.reason = result.reason or "finish called without verified success"
                break
        if result.finished or result.tool_errors >= max_tool_errors:
            break
        await _observe(ctx, messages, result)

    if not result.finished and result.steps >= limit:
        result.reason = result.reason or "maximum agent steps reached"
    elif not result.finished and time.monotonic() - started >= wall_clock_timeout_s:
        result.reason = result.reason or "agent wall-clock timeout"
    ctx.evidence.log_event("agent_stop", {"success": result.success, "finished": result.finished, "steps": result.steps, "reason": result.reason})
    return result
