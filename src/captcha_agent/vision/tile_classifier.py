"""Tile classification interfaces and local/Anthropic implementations."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class TileVerdict:
    match: bool
    confidence: float
    reason: str


class TileClassifier(Protocol):
    async def matches(self, label: str, tile_png: bytes) -> TileVerdict:
        ...


def parse_tile_response(text: str) -> TileVerdict:
    candidate = text.strip()
    if "```" in candidate:
        candidate = candidate.replace("```json", "").replace("```", "").strip()
    try:
        value = json.loads(candidate)
        if not isinstance(value, dict):
            raise ValueError("response is not an object")
        confidence = max(0.0, min(1.0, float(value.get("confidence", 0))))
        return TileVerdict(bool(value.get("match", False)), confidence, str(value.get("reason", "")))
    except (TypeError, ValueError, json.JSONDecodeError):
        return TileVerdict(False, 0.0, "invalid classifier JSON")


class AnthropicTileClassifier:
    def __init__(self, model: str | None = None, timeout_s: float = 15.0):
        self.model = model or os.getenv("LLM_MODEL", "claude-3-5-sonnet-latest")
        self.timeout_s = timeout_s
        self._client: Any = None

    async def matches(self, label: str, tile_png: bytes) -> TileVerdict:
        if not os.getenv("ANTHROPIC_API_KEY"):
            return TileVerdict(False, 0.0, "ANTHROPIC_API_KEY is missing")
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        import base64

        image_data = base64.b64encode(tile_png).decode("ascii")
        prompt = f"Does this image contain a {label}? Answer JSON {{match, confidence, reason}}"
        for attempt in range(3):
            try:
                response = await asyncio.wait_for(
                    self._client.messages.create(
                        model=self.model,
                        max_tokens=128,
                        system="Return only valid JSON.",
                        messages=[{"role": "user", "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_data}},
                            {"type": "text", "text": prompt},
                        ]}],
                    ),
                    timeout=self.timeout_s,
                )
                text = " ".join(getattr(block, "text", "") for block in response.content)
                return parse_tile_response(text)
            except Exception as exc:
                if attempt == 2:
                    return TileVerdict(False, 0.0, f"classifier request failed: {exc}")
        return TileVerdict(False, 0.0, "classifier request failed")


class FakeTileClassifier:
    """Test classifier using injected answers keyed by tile index."""

    def __init__(self, answers: dict[int, bool]):
        self.answers = dict(answers)
        self._next_index = 0
        self._lock = asyncio.Lock()

    async def matches(self, label: str, tile_png: bytes) -> TileVerdict:
        async with self._lock:
            index = self._next_index
            self._next_index += 1
        return await self.matches_at(index, label, tile_png)

    async def matches_at(self, index: int, label: str, tile_png: bytes) -> TileVerdict:
        match = bool(self.answers.get(index, False))
        reason = "injected test answer" if index in self.answers else "no injected answer"
        return TileVerdict(match, 1.0 if index in self.answers else 0.0, reason)


async def classify_tiles(classifier: TileClassifier, label: str, tiles: list[bytes]) -> list[TileVerdict]:
    semaphore = asyncio.Semaphore(4)

    async def classify(index: int, tile_png: bytes) -> TileVerdict:
        async with semaphore:
            matches_at = getattr(classifier, "matches_at", None)
            if matches_at is not None:
                return await matches_at(index, label, tile_png)
            return await classifier.matches(label, tile_png)

    return await asyncio.gather(*(classify(index, tile) for index, tile in enumerate(tiles)))
