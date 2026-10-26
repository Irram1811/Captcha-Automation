"""Deterministic CAPTCHA-agent pipeline."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from .browser import BrowserSession
from .config import AppConfig, load_config
from .evidence import EvidenceRecorder
from .models import RunReport, ToolResult
from .report import write_report
from .agent.llm_client import AnthropicClient, LocalMockLLM
from .agent.loop import run as run_agent
from .tools import RunContext
from .tools.click_checkbox import tool as click_checkbox
from .tools.detect_widget import tool as detect_widget
from .tools.finish import tool as finish
from .tools.observe import tool as observe
from .tools.open_target import tool as open_target
from .tools.solve_slider import tool as solve_slider
from .tools.solve_image_grid import tool as solve_image_grid
from .tools.verify_result import tool as verify_result


def _run_id(target_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    return f"{stamp}_{target_id}"


async def _step(ctx: RunContext, name: str, handler, **args) -> ToolResult:
    ctx.evidence.log_event("step_start", {"step": name, "args": args})
    try:
        result = await handler(ctx, **args)
    except Exception as exc:
        result = ToolResult(ok=False, error=str(exc))
    ctx.evidence.log_event("step_result", {"step": name, "result": result.model_dump()})
    return result


async def run(
    target_id: str,
    mode: str = "deterministic",
    headed: bool = False,
    max_steps: int | None = None,
    config: AppConfig | None = None,
    mock: bool = False,
) -> RunReport:
    """Run one target and return an evidence-backed report."""
    if mode not in {"deterministic", "agent"}:
        raise ValueError("mode must be deterministic or agent")
    app_config = config or load_config()
    target = app_config.target_by_id(target_id)
    run_id = _run_id(target_id)
    settings = app_config.settings.model_copy(
        update={"headless": not headed, **({"max_steps": max_steps} if max_steps else {})}
    )
    evidence = EvidenceRecorder(settings.run_dir, run_id)
    started = time.monotonic()
    steps = 0
    attempted_tool: str | None = None
    reason: str | None = None
    mismatch = False
    success = False
    detected = None
    details: dict[str, object] = {}

    async with BrowserSession(run_id, settings, evidence) as session:
        ctx = RunContext(session, app_config, evidence)
        if mode == "agent":
            steps += 1
            opened = await _step(ctx, "open_target", open_target, target_id=target_id)
            if not opened.ok:
                reason = opened.error or "open_target failed"
            else:
                client = LocalMockLLM() if mock else AnthropicClient()
                agent_result = await run_agent(ctx, client, max_steps=settings.max_steps)
                steps += agent_result.steps
                attempted_tool = agent_result.attempted_tool
                detected = ctx.detection
                mismatch = detected is not None and detected.widget != target.expected_widget
                success = agent_result.success and agent_result.finished and not mismatch
                reason = agent_result.reason
                if mismatch:
                    reason = f"detected {detected.widget}, expected {target.expected_widget}"
                    evidence.log_event("widget_mismatch", {"reason": reason})
        else:
            for name, handler, args in (
                ("open_target", open_target, {"target_id": target_id}),
                ("observe", observe, {}),
                ("detect_widget", detect_widget, {}),
            ):
                steps += 1
                step_result = await _step(ctx, name, handler, **args)
                if not step_result.ok:
                    reason = step_result.error or f"{name} failed"
                    break
            if reason is None:
                detected = ctx.detection
                mismatch = detected is None or detected.widget != target.expected_widget
                if mismatch:
                    reason = f"detected {detected.widget if detected else 'unknown'}, expected {target.expected_widget}"
                    evidence.log_event("widget_mismatch", {"reason": reason})
                if detected is not None:
                    if detected.widget == "checkbox":
                        attempted_tool, action_handler = "click_checkbox", click_checkbox
                        steps += 1
                        action = await _step(ctx, attempted_tool, action_handler)
                    elif detected.widget == "slider":
                        attempted_tool, action_handler = "solve_slider", solve_slider
                        steps += 1
                        action = await _step(ctx, attempted_tool, action_handler)
                    elif detected.widget == "image_grid":
                        attempted_tool, action_handler = "solve_image_grid", solve_image_grid
                        steps += 1
                        action = await _step(ctx, attempted_tool, action_handler)
                    elif detected.widget == "unknown":
                        attempted_tool = "skip"
                        reason = "unsupported widget, human review required"
                        action = ToolResult(ok=False, error=reason)
                        evidence.log_event("step_result", {"step": "skip", "result": action.model_dump()})
                    else:
                        attempted_tool = "skip"
                        action = ToolResult(ok=target.expected_widget == "none", data={"reason": "no CAPTCHA detected"})
                        reason = reason or "no CAPTCHA detected"
                        evidence.log_event("step_result", {"step": "skip", "result": action.model_dump()})
                    if not action.ok and reason is None:
                        reason = action.error or f"{attempted_tool} failed"
                    if isinstance(action.data, dict):
                        if attempted_tool == "solve_image_grid":
                            details["image_grid"] = action.data
                            details["attempts"] = len(action.data.get("attempts", []))
                        elif attempted_tool == "solve_slider":
                            details["attempts"] = len(action.data.get("attempts", []))
                    if (
                        detected.widget == "image_grid"
                        and action.error
                        and (
                            "no tile classifier" in action.error.lower()
                            or "anthropic_api_key is missing" in action.error.lower()
                        )
                    ):
                        details["verdict"] = "SKIPPED"
                if detected is not None and detected.widget in {"image_grid", "unknown"}:
                    success = False
                else:
                    steps += 1
                    verification = await _step(ctx, "verify_result", verify_result)
                    success = verification.ok and (target.expected_widget == "none" or not mismatch)
                    if not success and reason is None:
                        reason = verification.error or "success rule was not satisfied"
                steps += 1
                finish_status = "skipped" if detected is not None and detected.widget in {"image_grid", "unknown"} else ("success" if success else "failure")
                await _step(ctx, "finish", finish, status=finish_status, summary=reason or "verified")

    duration = time.monotonic() - started
    report_path = evidence.run_dir / "report.json"
    report = RunReport(
        run_id=run_id,
        target_id=target_id,
        mode=mode,
        detected=detected,
        attempted_tool=attempted_tool,
        success=success,
        widget_mismatch=mismatch,
        reason=reason,
        steps=steps,
        duration_s=duration,
        artifacts=list(evidence.artifacts) + [str(report_path)],
        details=details,
    )
    write_report(report, evidence.run_dir)
    return report
