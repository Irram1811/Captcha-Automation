import json
import os
from pathlib import Path

import pytest

from captcha_agent.browser import BrowserSession
from captcha_agent.config import load_config
from captcha_agent.evidence import EvidenceRecorder
from captcha_agent.tools import RunContext
from captcha_agent.tools.solve_image_grid import tool as solve_image_grid
from captcha_agent.tools.verify_result import tool as verify_result
from captcha_agent.vision.tile_classifier import FakeTileClassifier


MANIFEST = Path(__file__).parents[1] / "fixtures" / "assets" / "grid" / "manifest.json"


def _answers_for_page(tile_indices: list[int], label: str) -> dict[int, bool]:
    manifest = json.loads(MANIFEST.read_text())
    return {
        index: manifest[f"tile_{tile_index:02d}.png"] == label
        for index, tile_index in enumerate(tile_indices)
    }


async def _context(fixture_server: str, tmp_path: Path, name: str):
    config = load_config()
    target = config.target_by_id("local_imagegrid").model_copy(
        update={"url": f"{fixture_server}imagegrid.html?seed=1"}
    )
    config = config.model_copy(update={"targets": [target]})
    settings = config.settings.model_copy(update={"run_dir": str(tmp_path)})
    evidence = EvidenceRecorder(tmp_path, name)
    session = BrowserSession(name, settings, evidence)
    await session.__aenter__()
    await session.page.goto(target.url)
    context = RunContext(session, config, evidence, target=target)
    return session, context


@pytest.mark.asyncio
async def test_image_grid_fake_classifier_reaches_verified(fixture_server: str, tmp_path: Path):
    session, context = await _context(fixture_server, tmp_path, "image-grid-correct")
    try:
        label = await context.page.locator("#label").text_content()
        indices = [int(value) for value in await context.page.locator(".tile").evaluate_all(
            "tiles => tiles.map(tile => tile.dataset.tileIndex)"
        )]
        context.state["tile_classifier"] = FakeTileClassifier(_answers_for_page(indices, label.strip()))
        result = await solve_image_grid(context, max_attempts=1)
        verified = await verify_result(context)
        assert result.ok is True
        assert verified.ok is True
    finally:
        await session.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_image_grid_wrong_answers_fail_cleanly(fixture_server: str, tmp_path: Path):
    session, context = await _context(fixture_server, tmp_path, "image-grid-wrong")
    try:
        count = await context.page.locator(".tile").count()
        context.state["tile_classifier"] = FakeTileClassifier({index: False for index in range(count)})
        result = await solve_image_grid(context, max_attempts=1)
        assert result.ok is False
        assert "verification failed" in (result.error or "").lower()
        assert (await context.page.locator("#status").text_content()).strip() == "try again"
    finally:
        await session.__aexit__(None, None, None)


@pytest.mark.asyncio
async def test_image_grid_refuses_non_local_page(tmp_path: Path):
    config = load_config()
    target = config.target_by_id("local_imagegrid").model_copy(
        update={"url": "https://example.com/imagegrid.html"}
    )
    config = config.model_copy(update={"targets": [target]})
    settings = config.settings.model_copy(update={"run_dir": str(tmp_path)})
    evidence = EvidenceRecorder(tmp_path, "image-grid-nonlocal")
    async with BrowserSession("image-grid-nonlocal", settings, evidence) as session:
        await session.page.set_content("<p>not a local fixture</p>")
        context = RunContext(session, config, evidence, target=target)
        context.state["tile_classifier"] = FakeTileClassifier({})
        result = await solve_image_grid(context)
    assert result.ok is False
    assert "localhost" in (result.error or "")


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY is not set")
async def test_live_anthropic_tile_classifier(fixture_server: str, tmp_path: Path):
    from captcha_agent.vision.tile_classifier import AnthropicTileClassifier

    tile = (MANIFEST.parent / "tile_00.png").read_bytes()
    result = await AnthropicTileClassifier().matches("circle", tile)
    assert 0.0 <= result.confidence <= 1.0
