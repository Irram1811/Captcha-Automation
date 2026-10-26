import json
from pathlib import Path

import pytest

from captcha_agent.browser import BrowserSession
from captcha_agent.config import load_config
from captcha_agent.evidence import EvidenceRecorder


@pytest.mark.asyncio
async def test_browser_session_records_evidence(tmp_path: Path, fixture_server: str):
    settings = load_config().settings.model_copy(update={"run_dir": str(tmp_path), "headless": True})
    evidence = EvidenceRecorder(tmp_path, "smoke")
    async with BrowserSession("smoke", settings, evidence) as session:
        assert session.page is not None
        await session.page.goto(f"{fixture_server}none.html")
        screenshot = await evidence.save_screenshot("page")
        evidence.log_event("opened", {"url": session.page.url})
        assert screenshot.exists()

    events = [json.loads(line) for line in (tmp_path / "smoke" / "events.jsonl").read_text().splitlines()]
    assert events[0]["type"] == "opened"
    assert (tmp_path / "smoke" / "trace.zip").exists()
