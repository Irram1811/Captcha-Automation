"""Markdown and JSON report rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import RunReport


def _events(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _verdict(report: RunReport) -> str:
    if report.details.get("verdict") == "SKIPPED":
        return "SKIPPED"
    reason = (report.reason or "").lower()
    skipped_reason = any(term in reason for term in ("missing api key", "anthropic_api_key is missing", "no tile classifier", "unknown widget", "not implemented", "skipped"))
    return "SKIPPED" if report.attempted_tool == "skip" or (report.detected and report.detected.widget in {"none", "unknown"}) or skipped_reason else ("PASS" if report.success else "FAIL")


def verdict(report: RunReport) -> str:
    """Return the report verdict used by renderers and CLI exit decisions."""
    if report.details.get("verdict") == "SKIPPED":
        return "SKIPPED"
    return _verdict(report)


def _image_grid_details(report: RunReport, events: list[dict[str, Any]]) -> dict[str, Any]:
    details = dict(report.details.get("image_grid", {}))
    tiles = list(details.get("tiles", []))
    prompt = details.get("prompt")
    attempt_records = details.get("attempts", [])
    if not isinstance(attempt_records, list):
        attempt_records = []
    for event in events:
        event_type = event.get("type", "")
        payload = event.get("payload", {}) or {}
        if event_type in {"image_grid_prompt", "solve_image_grid_prompt"}:
            prompt = payload.get("prompt", payload.get("label", prompt))
        if event_type in {"image_grid_attempt", "solve_image_grid_attempt"}:
            attempt_number = payload.get("attempt")
            if not any(item.get("attempt") == attempt_number for item in attempt_records):
                attempt_records.append(dict(payload))
            prompt = payload.get("prompt", prompt)
            if payload.get("tiles"):
                tiles = list(payload["tiles"])
    attempts = len(attempt_records)
    if not attempts:
        raw_attempts = details.get("attempts", 0)
        attempts = int(raw_attempts) if isinstance(raw_attempts, int) else 0
    normalized_tiles = []
    for index, tile in enumerate(tiles):
        verdict = tile.get("verdict", tile.get("match", False))
        clicked = tile.get("clicked", False)
        normalized_tiles.append({
            "index": tile.get("index", index),
            "verdict": verdict,
            "confidence": tile.get("confidence", 0.0),
            "clicked": clicked if isinstance(clicked, str) else ("yes" if clicked else "no"),
            "reason": tile.get("reason", ""),
        })
    before_after = [
        {"before": item.get("before"), "after": item.get("after"), "attempt": item.get("attempt")}
        for item in attempt_records
        if item.get("before") or item.get("after")
    ]
    return {
        "prompt": prompt,
        "tiles": normalized_tiles,
        "attempts": attempts,
        "attempt_records": attempt_records,
        "before_after": before_after,
    }


def render_markdown(report: RunReport, run_dir: str | Path) -> str:
    """Render a report using paths relative to the run directory."""
    root = Path(run_dir)
    events = _events(root)
    detected = report.detected
    tools: list[str] = []
    for event in events:
        if event.get("type") == "step_start":
            name = event.get("payload", {}).get("step")
            if name and name not in tools:
                tools.append(name)
        if event.get("type") == "agent_tool_call":
            name = event.get("payload", {}).get("name")
            if name and name not in tools:
                tools.append(name)

    attempts: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") == "solve_slider_attempt":
            attempts.append(dict(event.get("payload", {})))
        elif event.get("type") == "solve_slider_outcome" and attempts:
            attempts[-1]["outcome"] = event.get("payload", {}).get("outcome", "unknown")
    for attempt in attempts:
        attempt.setdefault("outcome", "recorded")

    verification = [
        event.get("payload", {}).get("evidence")
        for event in events
        if event.get("type") == "verify_result" and event.get("payload", {}).get("evidence")
    ]
    decisions = [event.get("payload", {}) for event in events if event.get("type") == "agent_tool_call"]
    screenshots = sorted(root.glob("screenshots/*.png"))
    image_grid = _image_grid_details(report, events) if detected and detected.widget == "image_grid" else None
    lines = [
        f"# CAPTCHA Run Report: `{report.run_id}`",
        "",
        f"- **Run ID:** `{report.run_id}`",
        f"- **Target:** `{report.target_id}`",
        f"- **Mode:** `{report.mode}`",
        f"- **Final verdict:** **{_verdict(report)}**",
        f"- **Duration:** `{report.duration_s:.3f}s`",
        f"- **Steps:** `{report.steps}`",
        "",
        "## Detection",
        "",
    ]
    if detected:
        lines.extend([f"- **Widget:** `{detected.widget}`", f"- **Confidence:** `{detected.confidence:.3f}`", "- **Evidence:"])
        lines.extend([f"  - {item}" for item in detected.evidence])
    else:
        lines.append("No widget detection was recorded.")
    lines.extend(["", "## Tools used", "", ", ".join(f"`{tool}`" for tool in tools) or "None", "", "## Slider attempts", ""])
    if attempts:
        lines.extend(["| Attempt | Predicted offset | Score | Outcome |", "|---:|---:|---:|---|"])
        for index, attempt in enumerate(attempts, 1):
            lines.append(f"| {attempt.get('attempt', index)} | {attempt.get('predicted_offset', '—')} | {attempt.get('confidence', '—')} | {attempt.get('outcome', 'recorded')} |")
    else:
        lines.append("No slider attempts recorded.")
    if image_grid is not None:
        lines.extend(["", "## Image-grid details", "", f"- **Prompt label:** `{image_grid.get('prompt') or '—'}`", f"- **Attempts:** `{image_grid.get('attempts', 0)}`", "", "| Tile | Verdict | Confidence | Clicked |", "|---:|---|---:|---|"])
        for index, tile in enumerate(image_grid.get("tiles", [])):
            verdict = tile.get("verdict", tile.get("match", "—"))
            clicked = tile.get("clicked", "—")
            if isinstance(clicked, bool):
                clicked = "yes" if clicked else "no"
            lines.append(f"| {tile.get('index', index)} | {verdict} | {tile.get('confidence', '—')} | {clicked} |")
        for item in image_grid.get("before_after", []):
            before = item.get("before")
            after = item.get("after")
            if before:
                lines.append(f"- Attempt {item.get('attempt', '—')} before: [{Path(str(before)).name}](screenshots/{Path(str(before)).name})")
            if after:
                lines.append(f"- Attempt {item.get('attempt', '—')} after: [{Path(str(after)).name}](screenshots/{Path(str(after)).name})")
        before = [path.name for path in screenshots if "before" in path.stem]
        after = [path.name for path in screenshots if "after" in path.stem]
        if before:
            lines.append(f"\nBefore screenshot: [screenshots/{before[0]}](screenshots/{before[0]})")
        if after:
            lines.append(f"\nAfter screenshot: [screenshots/{after[-1]}](screenshots/{after[-1]})")
    lines.extend(["", "## Verification", ""])
    lines.extend([f"- {item}" for item in verification] or ["No verification evidence recorded."])
    if report.reason:
        lines.extend(["", f"**Reason:** {report.reason}"])
    if decisions:
        lines.extend(["", "## Agent decision log", "", "| Tool | Arguments | Rationale | Result |", "|---|---|---|---|"])
        for decision in decisions:
            result = decision.get("result", {})
            lines.append(
                f"| `{decision.get('name', '—')}` | `{json.dumps(decision.get('arguments', {}), separators=(',', ':'))}` | "
                f"{decision.get('rationale', '—')} | `{json.dumps(result, separators=(',', ':'))}` |"
            )
    lines.extend(["", "## Artifacts", ""])
    lines.extend([f"- [Screenshot: `{path.name}`](screenshots/{path.name})" for path in screenshots])
    lines.extend(["- [Events](events.jsonl)", "- [Trace](trace.zip)", "", "View the trace with:", "", "```bash", "npx playwright show-trace trace.zip", "```"])
    return "\n".join(lines) + "\n"


def write_report(report: RunReport, run_dir: str | Path) -> tuple[Path, Path]:
    root = Path(run_dir)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "report.json"
    markdown_path = root / "report.md"
    payload = report.model_dump()
    payload["verdict"] = _verdict(report)
    if report.detected and report.detected.widget == "image_grid":
        payload["image_grid"] = _image_grid_details(report, _events(root))
    json_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report, root), encoding="utf-8")
    return json_path, markdown_path


def write_summary(reports: list[RunReport], summary_path: str | Path) -> Path:
    path = Path(summary_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# CAPTCHA Run Summary", "", "| Target | Mode | Widget detected | Tool used | Verdict | Attempts | Duration | Report |", "|---|---|---|---|---|---:|---:|---|"]
    for report in reports:
        verdict = _verdict(report)
        attempts = report.details.get("attempts", 0)
        lines.append(f"| `{report.target_id}` | `{report.mode}` | `{report.detected.widget if report.detected else 'unknown'}` | `{report.attempted_tool or '—'}` | **{verdict}** | {attempts} | {report.duration_s:.3f}s | [{report.run_id}](./{report.run_id}/report.md) |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
