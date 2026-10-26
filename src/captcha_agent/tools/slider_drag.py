"""Shared timing-sensitive drag primitives for the local slider fixture."""

from __future__ import annotations

import asyncio
import random
from typing import Any


async def wait_for_slider_images(page: Any, timeout_ms: int) -> None:
    """Wait until the background canvas and puzzle image have been painted."""
    await page.wait_for_function(
        """() => {
          const background = document.querySelector('#bg, #scene');
          const piece = document.querySelector('#piece');
          if (!background || !piece || !piece.complete || piece.naturalWidth <= 0) return false;
          const backgroundRect = background.getBoundingClientRect();
          const pieceRect = piece.getBoundingClientRect();
          if (backgroundRect.width <= 0 || backgroundRect.height <= 0 || pieceRect.width <= 0 || pieceRect.height <= 0) return false;
          if (background.tagName.toLowerCase() === 'img') {
            return background.complete && background.naturalWidth > 0;
          }
          const context = background.getContext('2d');
          if (!context || !background.width || !background.height) return false;
          const pixels = context.getImageData(0, 0, background.width, background.height).data;
          for (let index = 0; index < pixels.length; index += 4) {
            if (pixels[index] || pixels[index + 1] || pixels[index + 2]) return true;
          }
          return false;
        }""",
        timeout=timeout_ms,
    )


async def drag_slider(page: Any, target_left: float) -> None:
    """Drag the local slider with enough events for the fixture to process."""
    handle = page.locator("#handle").first
    handle_box = await handle.bounding_box()
    track_box = await page.locator("#track").first.bounding_box()
    if not handle_box or not track_box:
        raise RuntimeError("Slider handle or track is not visible")
    start_x = handle_box["x"] + handle_box["width"] / 2
    start_y = handle_box["y"] + handle_box["height"] / 2
    max_handle_left = track_box["width"] - handle_box["width"]
    handle_left = max(0.0, min(max_handle_left, target_left))
    end_x = track_box["x"] + handle_left + handle_box["width"] / 2
    mouse_down = False
    try:
        await page.mouse.move(start_x, start_y)
        await page.mouse.down()
        mouse_down = True
        steps = max(25, random.randint(25, 30))
        for index in range(1, steps + 1):
            progress = index / steps
            eased = 1 - (1 - progress) ** 2
            jitter = random.uniform(-0.7, 0.7) if index < steps else 0.0
            await page.mouse.move(
                start_x + (end_x - start_x) * eased + jitter,
                start_y + random.uniform(-0.5, 0.5),
            )
            await asyncio.sleep(random.uniform(0.01, 0.03))
        await page.mouse.move(end_x, start_y)
        await asyncio.sleep(0.1)
    finally:
        if mouse_down:
            await page.mouse.up()
