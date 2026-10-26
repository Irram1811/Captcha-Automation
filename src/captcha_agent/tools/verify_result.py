"""Evaluate a configured success rule independently."""

from pydantic import BaseModel, ConfigDict

from ..errors import VerificationFailed
from ..models import ToolResult
from .context import RunContext


class VerifyResultArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


async def tool(ctx: RunContext, **args) -> ToolResult:
    VerifyResultArgs.model_validate(args)
    if ctx.target is None:
        return ToolResult(ok=False, error="No target has been opened")
    rule = ctx.target.success
    try:
        if rule.kind == "selector_text":
            observed = (await ctx.page.locator(rule.selector).first.text_content() or "").strip()
            matched = observed == str(rule.expected)
        elif rule.kind == "selector_visible":
            locator = ctx.page.locator(rule.selector).first
            observed = await locator.is_visible()
            matched = observed == (True if rule.expected is None else bool(rule.expected))
        elif rule.kind == "js_flag":
            observed = await ctx.page.evaluate(f"() => Boolean({rule.expr})")
            matched = observed == (True if rule.expected is None else bool(rule.expected))
        else:
            locator = ctx.page.locator(rule.selector).first
            observed = await locator.input_value()
            matched = bool(observed) if rule.expected is None else observed == str(rule.expected)
        evidence = f"{rule.kind}: observed={observed!r}, expected={rule.expected!r}"
        ctx.evidence.log_event("verify_result", {"ok": matched, "evidence": evidence})
        error = None if matched else f"{VerificationFailed.__name__}: {evidence}"
        return ToolResult(ok=matched, data={"evidence": evidence}, error=error)
    except Exception as exc:
        return ToolResult(ok=False, error=str(exc))
