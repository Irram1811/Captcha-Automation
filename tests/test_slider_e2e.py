from pathlib import Path

import pytest

from captcha_agent.browser import BrowserSession
from captcha_agent.config import load_config
from captcha_agent.evidence import EvidenceRecorder
from captcha_agent.tools import RunContext
from captcha_agent.tools.solve_slider import tool as solve_slider
from captcha_agent.tools.verify_result import tool as verify_result


@pytest.mark.asyncio
async def test_slider_random_load_success_rate(fixture_server: str, tmp_path: Path):
    config = load_config()
    target = config.target_by_id("local_slider").model_copy(update={"url": f"{fixture_server}slider.html"})
    config = config.model_copy(update={"targets": [target]})
    settings = config.settings.model_copy(update={"run_dir": str(tmp_path), "max_slider_attempts": 3})
    successes = 0
    runs = 20
    async with BrowserSession("slider-e2e", settings, EvidenceRecorder(tmp_path, "slider-e2e")) as session:
        assert session.page is not None
        context = RunContext(session, config, session.evidence, target=target)
        for index in range(runs):
            await session.page.goto(f"{fixture_server}slider.html?seed={index}")
            result = await solve_slider(context)
            verified = await verify_result(context) if result.ok else result
            successes += int(verified.ok)
    print(f"slider success rate: {successes}/{runs}")
    assert successes / runs >= 0.6


@pytest.mark.asyncio
async def test_slider_seed_changes_gap(fixture_server: str, tmp_path: Path):
    config = load_config()
    settings = config.settings.model_copy(update={"run_dir": str(tmp_path)})
    evidence = EvidenceRecorder(tmp_path, "slider-seed")
    async with BrowserSession("slider-seed", settings, evidence) as session:
        assert session.page is not None
        await session.page.goto(f"{fixture_server}slider.html?seed=1")
        first = await session.page.locator("#slider").get_attribute("data-gap-x")
        await session.page.goto(f"{fixture_server}slider.html?seed=2")
        second = await session.page.locator("#slider").get_attribute("data-gap-x")
    assert first != second
