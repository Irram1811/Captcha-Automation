"""Compact page observation for agent reasoning."""

from typing import Any

from pydantic import BaseModel, ConfigDict

from ..models import ToolResult
from .context import RunContext


class ObserveArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


async def tool(ctx: RunContext, **args) -> ToolResult:
    ObserveArgs.model_validate(args)
    screenshot = await ctx.evidence.save_screenshot("observe")
    summary: dict[str, Any] = await ctx.page.evaluate(
        """() => {
          const visible = (el) => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
          };
          const selector = (el) => {
            if (el.id) return `#${CSS.escape(el.id)}`;
            if (el.getAttribute('name')) return `${el.tagName.toLowerCase()}[name="${el.getAttribute('name')}"]`;
            const role = el.getAttribute('role');
            if (role) return `${el.tagName.toLowerCase()}[role="${role}"]`;
            return el.tagName.toLowerCase();
          };
          const elements = [...document.querySelectorAll('button, input, select, textarea, a, [role], [draggable="true"], canvas')]
            .filter(visible).slice(0, 60).map((el) => ({
              role: el.getAttribute('role') || el.tagName.toLowerCase(),
              text: (el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').trim().slice(0, 120),
              selector: selector(el)
            }));
          return {
            title: document.title,
            url: location.href,
            interactive: elements,
            iframes: [...document.querySelectorAll('iframe')].slice(0, 60).map((f) => f.src)
          };
        }"""
    )
    ctx.evidence.log_event("observe", {"interactive_count": len(summary["interactive"])})
    return ToolResult(ok=True, data=summary, screenshot_path=str(screenshot))
