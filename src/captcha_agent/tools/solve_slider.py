"""Visually solve the self-hosted slider fixture."""

from __future__ import annotations

import base64

from pydantic import BaseModel, ConfigDict

from ..models import ToolResult
from ..vision.slider_gap import GapResult, find_gap_offset
from .context import RunContext
from .slider_drag import drag_slider, wait_for_slider_images


class SolveSliderArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


async def _canvas_png(ctx: RunContext, selector: str) -> bytes:
    data_url = await ctx.page.evaluate(
        """(selector) => {
          const canvas = document.querySelector(selector);
          if (!canvas) throw new Error(`Canvas not found: ${selector}`);
          return canvas.toDataURL('image/png');
        }""",
        selector,
    )
    return base64.b64decode(data_url.split(",", 1)[1])


async def _element_png(ctx: RunContext, selector: str) -> bytes:
    """Render an image into a transparent canvas without flattening alpha."""
    data_url = await ctx.page.evaluate(
        """(selector) => {
          const image = document.querySelector(selector);
          if (!image || !image.complete || !image.naturalWidth) {
            throw new Error(`Image not loaded: ${selector}`);
          }
          const canvas = document.createElement('canvas');
          canvas.width = image.naturalWidth;
          canvas.height = image.naturalHeight;
          canvas.getContext('2d').drawImage(image, 0, 0);
          return canvas.toDataURL('image/png');
        }""",
        selector,
    )
    return base64.b64decode(data_url.split(",", 1)[1])


async def _wait_for_puzzle(ctx: RunContext) -> None:
    """Wait until the fixture has painted both the background and piece."""
    await wait_for_slider_images(ctx.page, ctx.config.settings.step_timeout_ms)


async def tool(ctx: RunContext, **args) -> ToolResult:
    SolveSliderArgs.model_validate(args)
    attempts: list[dict[str, object]] = []
    max_attempts = ctx.config.settings.max_slider_attempts
    bg_locator = ctx.page.locator("#scene").first
    piece_locator = ctx.page.locator("#piece").first
    for attempt in range(1, max_attempts + 1):
        try:
            await _wait_for_puzzle(ctx)
            bg_png = await _canvas_png(ctx, "#scene")
            piece_png = await _element_png(ctx, "#piece")
            bg_box = await bg_locator.bounding_box()
            piece_box = await piece_locator.bounding_box()
            track_box = await ctx.page.locator("#track").first.bounding_box()
            handle_box = await ctx.page.locator("#handle").first.bounding_box()
            if not bg_box or not piece_box or not track_box or not handle_box:
                raise RuntimeError("Slider geometry is not visible")
            result: GapResult = find_gap_offset(bg_png, piece_png, scale=1.0)
            # Screenshots are already rendered pixels; convert the image x into
            # the track's CSS travel distance without using the hidden gap attr.
            bg_width = max(1.0, float(bg_box["width"]))
            piece_width = float(piece_box["width"])
            target_left = result.x / max(1.0, bg_width - piece_width) * (track_box["width"] - handle_box["width"])
            await ctx.evidence.save_screenshot(f"solve_slider_attempt_{attempt}")
            await drag_slider(ctx.page, target_left)
            try:
                await ctx.page.wait_for_function(
                    "() => ['verified', 'try again'].includes((document.querySelector('#status')?.textContent || '').trim())",
                    timeout=1500,
                )
            except Exception:
                pass
            status = (await ctx.page.locator("#status").text_content() or "").strip()
            final_piece_x = float(await ctx.page.locator("#piece").evaluate("element => parseFloat(element.style.left) || 0"))
            attempt_data = {
                "attempt": attempt,
                "predicted_offset": result.x,
                "confidence": result.confidence,
                "drag_distance": target_left,
                "final_piece_x": final_piece_x,
                "status": status,
            }
            attempts.append(attempt_data)
            ctx.evidence.log_event("solve_slider_attempt", attempt_data)
            if status == "verified":
                ctx.evidence.log_event("solve_slider_outcome", {"attempt": attempt, "outcome": "success"})
                screenshot = await ctx.evidence.save_screenshot("solve_slider_success")
                return ToolResult(ok=True, data={"attempts": attempts}, screenshot_path=str(screenshot))
            ctx.evidence.log_event("solve_slider_outcome", {"attempt": attempt, "outcome": status or "timeout"})
            if attempt < max_attempts:
                continue
            break
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            ctx.evidence.log_event("solve_slider_error", {"attempt": attempt, "error": error})
            if attempt == max_attempts:
                return ToolResult(ok=False, data={"attempts": attempts}, error=error)
    return ToolResult(ok=False, data={"attempts": attempts}, error="Slider could not be solved")
