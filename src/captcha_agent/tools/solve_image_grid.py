"""Solve the self-hosted image-grid fixture with an injected classifier."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from ..allowlist import assert_allowed
from ..errors import AllowlistError
from ..models import ToolResult
from ..vision.tile_classifier import AnthropicTileClassifier, TileClassifier, classify_tiles
from .context import RunContext


class SolveImageGridArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_confidence: float = Field(default=0.6, ge=0, le=1)
    max_attempts: int = Field(default=2, gt=0)


def _classifier(ctx: RunContext) -> TileClassifier | None:
    injected = ctx.state.get("tile_classifier")
    if injected is not None:
        return injected
    if ctx.config.settings.tile_classifier == "anthropic" and os.getenv("ANTHROPIC_API_KEY"):
        return AnthropicTileClassifier()
    return None


async def tool(ctx: RunContext, **args) -> ToolResult:
    parsed = SolveImageGridArgs.model_validate(args)
    if ctx.target is None:
        return ToolResult(ok=False, error="No target is open")
    try:
        assert_allowed(ctx.target.url, ctx.config)
    except AllowlistError as exc:
        return ToolResult(ok=False, error=f"AllowlistError: {exc}")
    if urlsplit(ctx.page.url).hostname not in {"127.0.0.1", "localhost"}:
        return ToolResult(ok=False, error="Image-grid solver only permits localhost or 127.0.0.1")
    classifier = _classifier(ctx)
    if classifier is None:
        return ToolResult(ok=False, error="ANTHROPIC_API_KEY is missing or no tile classifier was injected")

    attempts: list[dict[str, object]] = []
    for attempt in range(1, parsed.max_attempts + 1):
        label = (await ctx.page.locator("#label").text_content() or "").strip()
        tiles = ctx.page.locator(".tile")
        count = await tiles.count()
        before = await ctx.evidence.save_screenshot(f"image_grid_before_{attempt}")
        tile_pngs = [await tiles.nth(index).locator("img").first.screenshot() for index in range(count)]
        verdicts = await classify_tiles(classifier, label, tile_pngs)
        rows: list[dict[str, object]] = []
        for index, verdict in enumerate(verdicts):
            clicked = verdict.match and verdict.confidence >= parsed.min_confidence
            if clicked:
                await tiles.nth(index).click()
            row = {"index": index, "match": verdict.match, "confidence": verdict.confidence, "reason": verdict.reason, "clicked": clicked}
            rows.append(row)
            ctx.evidence.log_event("image_grid_tile", row)
        await ctx.page.get_by_role("button", name="Verify").click()
        await ctx.page.wait_for_function(
            "() => ['verified', 'try again'].includes((document.querySelector('#status')?.textContent || '').trim())",
            timeout=ctx.config.settings.step_timeout_ms,
        )
        status = (await ctx.page.locator("#status").text_content() or "").strip()
        after = await ctx.evidence.save_screenshot(f"image_grid_after_{attempt}")
        payload = {"attempt": attempt, "prompt": label, "tiles": rows, "status": status, "before": str(before), "after": str(after)}
        attempts.append(payload)
        ctx.evidence.log_event("image_grid_attempt", payload)
        if status == "verified":
            return ToolResult(ok=True, data={"prompt": label, "attempts": attempts}, screenshot_path=str(after))
    return ToolResult(ok=False, data={"attempts": attempts}, error="Image-grid verification failed")
