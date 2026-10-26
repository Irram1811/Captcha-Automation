"""Measure deterministic rates for the self-hosted slider and image-grid fixtures."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from aiohttp import web
from rich.console import Console
from rich.table import Table

from captcha_agent.browser import BrowserSession
from captcha_agent.config import load_config
from captcha_agent.evidence import EvidenceRecorder
from captcha_agent.models import RunReport
from captcha_agent.report import write_report
from captcha_agent.tools import RunContext
from captcha_agent.tools.detect_widget import tool as detect_widget
from captcha_agent.tools.solve_image_grid import tool as solve_image_grid
from captcha_agent.tools.solve_slider import tool as solve_slider
from captcha_agent.tools.verify_result import tool as verify_result
from captcha_agent.vision.tile_classifier import AnthropicTileClassifier, FakeTileClassifier, TileClassifier
from fixtures.server import create_app

console = Console()
GRID_MANIFEST = ROOT / "fixtures" / "assets" / "grid" / "manifest.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--widget", choices=("slider", "image_grid", "all"), default="all")
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--out", type=Path, default=Path("runs/rates.md"))
    parser.add_argument("--headed", action="store_true")
    return parser


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _start_server(port: int) -> web.AppRunner:
    runner = web.AppRunner(create_app())
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", port).start()
    return runner


def _manifest() -> dict[str, str]:
    return json.loads(GRID_MANIFEST.read_text(encoding="utf-8"))


def _merge_measurements(
    previous: dict[str, object],
    new_rows: list[dict[str, object]],
    new_records: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Merge measurements by widget and classifier, replacing only new keys."""
    rows_by_key: dict[tuple[str, str], dict[str, object]] = {}
    for row in previous.get("rows", []) if isinstance(previous.get("rows", []), list) else []:
        if isinstance(row, dict):
            rows_by_key[(str(row.get("widget")), str(row.get("classifier", "—")))] = row
    for row in new_rows:
        rows_by_key[(str(row["widget"]), str(row.get("classifier", "—")))] = row

    classifiers = {
        str(row.get("widget")): str(row.get("classifier", "—"))
        for row in rows_by_key.values()
        if isinstance(row, dict)
    }
    records_by_key: dict[tuple[str, str, object], dict[str, object]] = {}
    old_records = previous.get("records", [])
    if isinstance(old_records, list):
        for record in old_records:
            if isinstance(record, dict):
                widget = str(record.get("widget"))
                classifier = str(record.get("classifier", classifiers.get(widget, "—")))
                records_by_key[(widget, classifier, record.get("seed"))] = record
    for record in new_records:
        widget = str(record.get("widget"))
        classifier = str(record.get("classifier", classifiers.get(widget, "—")))
        record["classifier"] = classifier
        records_by_key[(widget, classifier, record.get("seed"))] = record
    return list(rows_by_key.values()), list(records_by_key.values())


def _seed_url(url: str, seed: int) -> str:
    parsed = urlsplit(url)
    query = f"{parsed.query}&seed={seed}" if parsed.query else f"seed={seed}"
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))


async def _fake_for_page(ctx: RunContext, label: str) -> FakeTileClassifier:
    manifest = _manifest()
    tile_indices = await ctx.page.locator(".tile").evaluate_all(
        "tiles => tiles.map(tile => Number(tile.dataset.tileIndex))"
    )
    answers = {
        index: manifest[f"tile_{tile_index:02d}.png"] == label
        for index, tile_index in enumerate(tile_indices)
    }
    return FakeTileClassifier(answers)


async def _one_run(config, target_id: str, seed: int, headed: bool, classifier: TileClassifier | None) -> RunReport:
    base_target = config.target_by_id(target_id)
    target = base_target.model_copy(update={"url": _seed_url(base_target.url, seed)})
    run_id = f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S-%f')}_{target_id}_{seed}"
    settings = config.settings.model_copy(update={"headless": not headed})
    evidence = EvidenceRecorder(settings.run_dir, run_id)
    started = time.monotonic()
    detected = None
    attempted_tool = None
    success = False
    reason = None
    details: dict[str, object] = {"attempts": 0}
    run_config = config.model_copy(update={"targets": [target]})
    async with BrowserSession(run_id, settings, evidence) as session:
        ctx = RunContext(session, run_config, evidence, target=target)
        await ctx.page.goto(target.url, wait_until="load", timeout=settings.step_timeout_ms)
        detection = await detect_widget(ctx)
        detected = ctx.detection
        if not detection.ok or detected is None or detected.widget != target.expected_widget:
            reason = f"detected {detected.widget if detected else 'unknown'}, expected {target.expected_widget}"
        elif target.expected_widget == "slider":
            attempted_tool = "solve_slider"
            action = await solve_slider(ctx)
            details["attempts"] = len((action.data or {}).get("attempts", [])) if isinstance(action.data, dict) else 0
            verification = await verify_result(ctx) if action.ok else action
            success = verification.ok
            reason = None if success else verification.error
        elif target.expected_widget == "image_grid" and classifier is not None:
            attempted_tool = "solve_image_grid"
            label = (await ctx.page.locator("#label").text_content() or "").strip()
            ctx.state["tile_classifier"] = await _fake_for_page(ctx, label) if isinstance(classifier, FakeTileClassifier) else classifier
            action = await solve_image_grid(ctx)
            details["image_grid"] = action.data or {}
            details["attempts"] = len((action.data or {}).get("attempts", [])) if isinstance(action.data, dict) else 0
            verification = await verify_result(ctx) if action.ok else action
            success = verification.ok
            reason = None if success else verification.error
        else:
            reason = "ANTHROPIC_API_KEY is missing; image-grid live measurement is pending"
    report = RunReport(
        run_id=run_id, target_id=target_id, mode="deterministic", detected=detected,
        attempted_tool=attempted_tool, success=success, reason=reason, steps=4,
        duration_s=time.monotonic() - started, artifacts=list(evidence.artifacts), details=details,
    )
    write_report(report, evidence.run_dir)
    return report


async def _measure(args: argparse.Namespace) -> dict[str, object]:
    if args.runs <= 0:
        raise ValueError("--runs must be greater than zero")
    if args.live and args.widget == "slider":
        raise ValueError("--live is supported only for image_grid")
    config = load_config()
    port = args.port or _free_port()
    runner = await _start_server(port) if args.port is None else None
    try:
        rewritten = []
        for target in config.targets:
            parsed = urlsplit(target.url)
            rewritten.append(target.model_copy(update={"url": urlunsplit((parsed.scheme, f"127.0.0.1:{port}", parsed.path, parsed.query, parsed.fragment))}))
        config = config.model_copy(update={"targets": rewritten})
        target_ids = (["local_slider"] if args.widget in {"slider", "all"} else []) + (["local_imagegrid"] if args.widget in {"image_grid", "all"} else [])
        classifier_name = "anthropic" if args.live else "fake"
        classifier: TileClassifier | None = None
        if args.live:
            if os.getenv("ANTHROPIC_API_KEY"):
                classifier = AnthropicTileClassifier()
            else:
                console.print("ANTHROPIC_API_KEY is missing; image-grid rows will be pending.")
        else:
            classifier = FakeTileClassifier({})
        rows: list[dict[str, object]] = []
        records: list[dict[str, object]] = []
        for target_id in target_ids:
            widget = "slider" if target_id == "local_slider" else "image_grid"
            if widget == "image_grid" and classifier is None:
                rows.append({"widget": widget, "classifier": classifier_name, "runs": args.runs, "successes": "pending", "rate": "pending", "median_duration_s": "pending", "failed_seeds": "pending"})
                records.extend({"widget": widget, "classifier": classifier_name, "seed": args.seed_start + offset, "verdict": "pending", "attempts": 0, "duration_s": "pending", "run_dir": ""} for offset in range(args.runs))
                continue
            reports = [await _one_run(config, target_id, args.seed_start + offset, args.headed, classifier) for offset in range(args.runs)]
            successes = sum(report.success for report in reports)
            failed = [args.seed_start + index for index, report in enumerate(reports) if not report.success]
            rows.append({"widget": widget, "classifier": classifier_name if widget == "image_grid" else "—", "runs": args.runs, "successes": successes, "rate": successes / args.runs, "median_duration_s": median(report.duration_s for report in reports), "failed_seeds": failed})
            records.extend({"widget": widget, "classifier": classifier_name if widget == "image_grid" else "—", "seed": args.seed_start + index, "verdict": "PASS" if report.success else "FAIL", "attempts": report.details.get("attempts", 0), "duration_s": report.duration_s, "run_dir": str(Path(config.settings.run_dir) / report.run_id)} for index, report in enumerate(reports))
        caveat = "Fake image-grid mode uses the generated manifest as a harness-side oracle and measures the click/verify pipeline, not vision accuracy. All measurements cover only self-hosted fixtures."
        previous: dict[str, object] = {}
        rates_json = args.out.with_suffix(".json")
        if rates_json.exists():
            try:
                loaded = json.loads(rates_json.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    previous = loaded
            except json.JSONDecodeError:
                previous = {}
        rows, records = _merge_measurements(previous, rows, records)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Fixture Measurement Rates", "", "| Widget | Classifier | Runs | Successes | Rate | Median duration (s) | Failed seeds |", "|---|---|---:|---:|---:|---:|---|"]
        for row in rows:
            rate = row["rate"] if isinstance(row["rate"], str) else f"{row['rate']:.2%}"
            duration = row["median_duration_s"] if isinstance(row["median_duration_s"], str) else f"{row['median_duration_s']:.3f}"
            lines.append(f"| {row['widget']} | {row['classifier']} | {row['runs']} | {row['successes']} | {rate} | {duration} | {row['failed_seeds']} |")
        lines.extend(["", f"Caveats: {caveat}", "", "Sanity expectation: fake image-grid mode should be 20/20; this is a note, not a gate."])
        args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        args.out.with_suffix(".json").write_text(json.dumps({"rows": rows, "records": records, "caveats": caveat}, indent=2) + "\n", encoding="utf-8")
        table = Table(title="Fixture Measurement Rates")
        for column in ("Widget", "Classifier", "Runs", "Successes", "Rate", "Median duration (s)", "Failed seeds"):
            table.add_column(column)
        for row in rows:
            table.add_row(*(str(row[key]) for key in ("widget", "classifier", "runs", "successes", "rate", "median_duration_s", "failed_seeds")))
        console.print(table)
        return {"rows": rows, "records": records}
    finally:
        if runner is not None:
            await runner.cleanup()


def main() -> None:
    asyncio.run(_measure(_parser().parse_args()))


if __name__ == "__main__":
    main()
