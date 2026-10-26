"""Open a configured target."""

from pydantic import BaseModel, ConfigDict, Field

from ..allowlist import assert_allowed
from ..models import ToolResult
from .context import RunContext


class OpenTargetArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: str = Field(min_length=1)


async def tool(ctx: RunContext, **args) -> ToolResult:
    parsed = OpenTargetArgs.model_validate(args)
    try:
        target = ctx.config.target_by_id(parsed.target_id)
        assert_allowed(target.url, ctx.config)
        await ctx.page.goto(target.url, wait_until="load", timeout=ctx.config.settings.step_timeout_ms)
        screenshot = await ctx.evidence.save_screenshot("open_target")
        ctx.target = target
        ctx.evidence.log_event("open_target", {"target_id": target.id, "url": target.url})
        return ToolResult(ok=True, data={"target_id": target.id, "url": ctx.page.url}, screenshot_path=str(screenshot))
    except Exception as exc:
        return ToolResult(ok=False, error=f"{type(exc).__name__}: {exc}")
