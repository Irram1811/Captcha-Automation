from pathlib import Path

import pytest

from captcha_agent.browser import BrowserSession
from captcha_agent.config import load_config
from captcha_agent.evidence import EvidenceRecorder
from captcha_agent.tools import RunContext
from captcha_agent.tools.detect_widget import tool as detect_widget


@pytest.mark.asyncio
async def test_detect_image_grid(fixture_server: str, tmp_path: Path):
    config = load_config()
    settings = config.settings.model_copy(update={"run_dir": str(tmp_path)})
    evidence = EvidenceRecorder(tmp_path, "detect-image-grid")
    async with BrowserSession("detect-image-grid", settings, evidence) as session:
        assert session.page is not None
        await session.page.goto(f"{fixture_server}imagegrid.html?seed=1")
        result = await detect_widget(RunContext(session, config, evidence))
    assert result.ok is True
    assert result.data["widget"] == "image_grid"
    assert result.data["confidence"] >= 0.9
    assert any("tile count: 16" in item for item in result.data["evidence"])


@pytest.mark.asyncio
async def test_detect_unknown_challenge_frame(fixture_server: str, tmp_path: Path):
    config = load_config()
    settings = config.settings.model_copy(update={"run_dir": str(tmp_path)})
    evidence = EvidenceRecorder(tmp_path, "detect-unknown")
    async with BrowserSession("detect-unknown", settings, evidence) as session:
        assert session.page is not None
        await session.page.set_content(
            '<iframe src="about:blank" title="captcha challenge" '
            'style="width:320px;height:180px;display:block"></iframe>'
        )
        result = await detect_widget(RunContext(session, config, evidence))
    assert result.ok is True
    assert result.data["widget"] == "unknown"
