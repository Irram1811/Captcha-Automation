from pathlib import Path

import pytest

from captcha_agent.browser import BrowserSession
from captcha_agent.config import load_config
from captcha_agent.evidence import EvidenceRecorder
from captcha_agent.models import Target
from captcha_agent.tools import RunContext
from captcha_agent.tools.detect_widget import tool as detect_widget
from captcha_agent.tools.open_target import tool as open_target
from captcha_agent.tools.click_checkbox import tool as click_checkbox
from captcha_agent.tools.verify_result import tool as verify_result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("page", "expected"),
    [("checkbox.html", "checkbox"), ("slider.html", "slider"), ("none.html", "none")],
)
async def test_detect_widget(fixture_server: str, tmp_path: Path, page: str, expected: str):
    config = load_config()
    settings = config.settings.model_copy(update={"run_dir": str(tmp_path)})
    evidence = EvidenceRecorder(tmp_path, f"detect-{expected}")
    async with BrowserSession(f"detect-{expected}", settings, evidence) as session:
        assert session.page is not None
        await session.page.goto(f"{fixture_server}{page}")
        result = await detect_widget(RunContext(session, config, evidence))
    assert result.ok is True
    assert result.data["widget"] == expected


@pytest.mark.asyncio
async def test_checkbox_flow(fixture_server: str, tmp_path: Path):
    config = load_config()
    target = config.target_by_id("local_checkbox").model_copy(update={"url": f"{fixture_server}checkbox.html"})
    config = config.model_copy(update={"targets": [target]})
    settings = config.settings.model_copy(update={"run_dir": str(tmp_path)})
    evidence = EvidenceRecorder(tmp_path, "checkbox-flow")
    async with BrowserSession("checkbox-flow", settings, evidence) as session:
        context = RunContext(session, config, evidence)
        opened = await open_target(context, target_id="local_checkbox")
        assert opened.ok is True
        clicked = await click_checkbox(context)
        assert clicked.ok is True
        verified = await verify_result(context)
        assert verified.ok is True
        assert "verified" in verified.data["evidence"]
