"""Collect diagnostic measurements for the local slider fixture.

This script intentionally reads ``data-gap-x`` only for diagnosis. It does not
change the solver or use the hidden value to compute the predicted offset.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import argparse
import asyncio
import base64
import socket
from typing import Any

from aiohttp import web
from playwright.async_api import TargetClosedError
from rich.console import Console
from rich.table import Table

from captcha_agent.browser import BrowserSession
from captcha_agent.config import load_config
from captcha_agent.evidence import EvidenceRecorder
from captcha_agent.tools.context import RunContext
from captcha_agent.tools.slider_drag import drag_slider, wait_for_slider_images
from captcha_agent.vision.slider_gap import find_gap_offset
from fixtures.server import create_app


OUT = ROOT / "runs" / "debug_slider"
console = Console()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def start_server(port: int) -> web.AppRunner:
    runner = web.AppRunner(create_app())
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    return runner


async def image_bytes(page: Any, selector: str) -> bytes:
    data_url = await page.evaluate(
        """(selector) => {
          const element = document.querySelector(selector);
          if (!element || !element.complete || !element.naturalWidth) {
            throw new Error(`Image not loaded: ${selector}`);
          }
          const canvas = document.createElement('canvas');
          canvas.width = element.naturalWidth;
          canvas.height = element.naturalHeight;
          canvas.getContext('2d').drawImage(element, 0, 0);
          return canvas.toDataURL('image/png');
        }""",
        selector,
    )
    return base64.b64decode(data_url.split(",", 1)[1])


async def canvas_bytes(page: Any) -> bytes:
    data_url = await page.evaluate(
        """() => document.querySelector('#scene').toDataURL('image/png')"""
    )
    return base64.b64decode(data_url.split(",", 1)[1])


async def debug_seed(page: Any, base_url: str, seed: int, out_dir: Path) -> dict[str, Any]:
    await page.goto(f"{base_url}/slider.html?seed={seed}", wait_until="load")
    await wait_for_slider_images(page, 10000)
    before = out_dir / f"seed_{seed}_before.png"
    after = out_dir / f"seed_{seed}_after.png"
    await page.screenshot(path=str(before), full_page=True)

    truth = int(await page.locator("#slider").get_attribute("data-gap-x"))
    bg_box = await page.locator("#scene").bounding_box()
    piece_box = await page.locator("#piece").bounding_box()
    track_box = await page.locator("#track").bounding_box()
    handle_box = await page.locator("#handle").bounding_box()
    if not bg_box or not piece_box or not track_box or not handle_box:
        raise RuntimeError("Slider geometry is not visible")
    natural = await page.evaluate("() => ({bg: document.querySelector('#scene').width, piece: document.querySelector('#piece').naturalWidth})")
    scale = piece_box["width"] / natural["piece"]
    result = find_gap_offset(await canvas_bytes(page), await image_bytes(page, "#piece"), scale=scale)
    max_travel = track_box["width"] - handle_box["width"]
    drag_distance = result.x / max(1.0, bg_box["width"] - piece_box["width"]) * max_travel
    handle_start = handle_box["x"] + handle_box["width"] / 2
    await drag_slider(page, drag_distance)
    try:
        await page.wait_for_function(
            "() => ['verified', 'try again'].includes((document.querySelector('#status')?.textContent || '').trim())",
            timeout=1500,
        )
    except Exception:
        pass
    piece_final = float(await page.locator("#piece").evaluate("(element) => parseFloat(element.style.left) || 0"))
    status = (await page.locator("#status").text_content() or "").strip()
    await page.screenshot(path=str(after), full_page=True)
    return {
        "seed": seed,
        "ground_truth_gap_x": truth,
        "predicted_offset": result.x,
        "match_score": round(result.confidence, 6),
        "natural_bg_width": natural["bg"],
        "rendered_bg_width": round(bg_box["width"], 3),
        "natural_piece_width": natural["piece"],
        "rendered_piece_width": round(piece_box["width"], 3),
        "scale_factor": round(scale, 6),
        "handle_start_x": round(handle_start, 3),
        "max_handle_travel": round(max_travel, 3),
        "computed_drag_distance": round(drag_distance, 3),
        "piece_final_x": round(piece_final, 3),
        "status": status,
    }


async def main(port: int | None) -> None:
    actual_port = port or free_port()
    runner = None
    if port is None:
        runner = await start_server(actual_port)
    OUT.mkdir(parents=True, exist_ok=True)
    config = load_config()
    settings = config.settings.model_copy(update={"headless": False, "run_dir": str(OUT)})
    evidence = EvidenceRecorder(OUT, "debug_slider")
    rows = []
    columns = [
        "seed", "ground_truth_gap_x", "predicted_offset", "match_score", "natural_bg_width",
        "rendered_bg_width", "scale_factor", "handle_start_x", "max_handle_travel",
        "computed_drag_distance", "piece_final_x", "status",
    ]
    try:
        async with BrowserSession("debug_slider", settings, evidence) as session:
            for seed in range(1, 6):
                try:
                    rows.append(await debug_seed(session.page, f"http://127.0.0.1:{actual_port}", seed, OUT))
                except TargetClosedError as exc:
                    rows.append({column: "—" for column in columns} | {"seed": seed, "status": f"TargetClosedError: {exc}"})
                    break
            table = Table(title="Slider diagnostics")
            for column in columns:
                table.add_column(column)
            for row in rows:
                table.add_row(*(str(row[column]) for column in columns))
            console.print(table)
            console.print(f"Screenshots: {OUT}")
            console.print("Diagnosis: pending until these measured rows are reviewed.")
    finally:
        if runner is not None:
            await runner.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(main(args.port))
