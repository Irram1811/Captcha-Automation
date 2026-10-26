import asyncio

import pytest

from captcha_agent.vision.tile_classifier import (
    TileVerdict,
    classify_tiles,
    parse_tile_response,
)


def test_parse_tile_response_accepts_json_and_code_fence():
    result = parse_tile_response('{"match": true, "confidence": 0.91, "reason": "circle"}')
    assert result == TileVerdict(True, 0.91, "circle")

    fenced = parse_tile_response('```json\n{"match": false, "confidence": 0.2, "reason": "no shape"}\n```')
    assert fenced == TileVerdict(False, 0.2, "no shape")


def test_parse_tile_response_bad_json_is_safe():
    result = parse_tile_response("not json")
    assert result.match is False
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_classify_tiles_limits_concurrency_to_four():
    active = 0
    maximum = 0

    class StubClassifier:
        async def matches(self, label: str, tile_png: bytes) -> TileVerdict:
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0.01)
            active -= 1
            return TileVerdict(True, 1.0, label)

    results = await classify_tiles(StubClassifier(), "circle", [b"tile"] * 12)
    assert len(results) == 12
    assert maximum <= 4
