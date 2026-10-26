from pathlib import Path

import pytest

from captcha_agent.agent.llm_client import FakeLLM, ToolCall
from captcha_agent.agent.loop import run as run_agent
from captcha_agent.browser import BrowserSession
from captcha_agent.config import load_config
from captcha_agent.evidence import EvidenceRecorder
from captcha_agent.tools import RunContext


def call(number: int, name: str, **arguments) -> ToolCall:
    return ToolCall(id=f"call-{number}", name=name, arguments=arguments)


async def make_context(fixture_server: str, tmp_path: Path):
    config = load_config()
    target = config.target_by_id("local_checkbox").model_copy(update={"url": f"{fixture_server}checkbox.html"})
    config = config.model_copy(update={"targets": [target]})
    settings = config.settings.model_copy(update={"run_dir": str(tmp_path), "max_steps": 20})
    evidence = EvidenceRecorder(tmp_path, "agent-test")
    session = BrowserSession("agent-test", settings, evidence)
    await session.__aenter__()
    return config, evidence, session, RunContext(session, config, evidence)


@pytest.mark.asyncio
async def test_agent_happy_path(fixture_server: str, tmp_path: Path):
    config, evidence, session, context = await make_context(fixture_server, tmp_path)
    try:
        llm = FakeLLM([
            call(1, "open_target", target_id="local_checkbox"),
            call(2, "detect_widget"),
            call(3, "click_checkbox"),
            call(4, "verify_result"),
            call(5, "finish", status="success", summary="verified"),
        ])
        result = await run_agent(context, llm)
        assert result.success is True
        assert result.finished is True
    finally:
        await session.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_agent_wrong_tool_then_recovers(fixture_server: str, tmp_path: Path):
    _, _, session, context = await make_context(fixture_server, tmp_path)
    try:
        llm = FakeLLM([
            call(1, "solve_slider"),
            call(2, "open_target", target_id="local_checkbox"),
            call(3, "detect_widget"),
            call(4, "click_checkbox"),
            call(5, "verify_result"),
            call(6, "finish", status="success", summary="verified"),
        ])
        result = await run_agent(context, llm)
        assert result.success is True
        assert result.tool_errors == 0
    finally:
        await session.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_agent_runaway_hits_max_steps(fixture_server: str, tmp_path: Path):
    _, _, session, context = await make_context(fixture_server, tmp_path)
    try:
        result = await run_agent(context, FakeLLM([call(i, "observe") for i in range(10)]), max_steps=3)
        assert result.success is False
        assert result.reason == "maximum agent steps reached"
        assert result.steps == 3
    finally:
        await session.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_agent_invalid_args_are_handled_gracefully(fixture_server: str, tmp_path: Path):
    _, _, session, context = await make_context(fixture_server, tmp_path)
    try:
        result = await run_agent(context, FakeLLM([call(i, "open_target") for i in range(3)]))
        assert result.success is False
        assert result.tool_errors == 3
        assert "Invalid tool call" in (result.reason or "")
    finally:
        await session.__aexit__(None, None, None)
