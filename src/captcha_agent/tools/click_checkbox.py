"""Click a checkbox CAPTCHA, including one embedded in an iframe."""

from pydantic import BaseModel, ConfigDict, Field

from ..errors import WidgetNotFound
from ..models import ToolResult
from .context import RunContext


class ClickCheckboxArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeout_ms: int | None = Field(default=None, gt=0)


async def tool(ctx: RunContext, **args) -> ToolResult:
    parsed = ClickCheckboxArgs.model_validate(args)
    timeout = parsed.timeout_ms or ctx.config.settings.step_timeout_ms
    selectors = ['[role="checkbox"]', 'text=I\'m not a robot', 'text=I’m not a robot']
    locator = None
    selected = None
    for candidate in selectors:
        direct = ctx.page.locator(candidate).first
        if await direct.count() and await direct.is_visible():
            locator, selected = direct, candidate
            break
    if locator is None:
        iframe_count = await ctx.page.locator("iframe").count()
        for index in range(iframe_count):
            frame = ctx.page.frame_locator("iframe").nth(index)
            for candidate in selectors:
                try:
                    nested = frame.locator(candidate).first
                    if await nested.count() and await nested.is_visible():
                        locator, selected = nested, f"iframe[{index}]:{candidate}"
                        break
                except Exception:
                    continue
            if locator is not None:
                break
    if locator is None:
        for frame in ctx.page.frames[1:]:
            for candidate in selectors:
                nested = frame.locator(candidate).first
                if await nested.count() and await nested.is_visible():
                    locator, selected = nested, f"iframe:{candidate}"
                    break
            if locator is not None:
                break
    if locator is None:
        error = WidgetNotFound("No visible checkbox CAPTCHA found")
        return ToolResult(ok=False, error=f"{type(error).__name__}: {error}")
    try:
        await locator.click(timeout=timeout)
        await ctx.page.wait_for_function("() => window.__captcha_solved === true", timeout=timeout)
        screenshot = await ctx.evidence.save_screenshot("click_checkbox")
        ctx.evidence.log_event("click_checkbox", {"selector": selected})
        return ToolResult(ok=True, data={"selector": selected}, screenshot_path=str(screenshot))
    except Exception as exc:
        return ToolResult(ok=False, error=f"{type(exc).__name__}: {exc}")
