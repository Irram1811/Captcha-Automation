"""Terminal conclusion tool."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..models import ToolResult
from .context import RunContext


class FinishArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "failure", "blocked"]
    summary: str = Field(min_length=1)


async def tool(ctx: RunContext, **args) -> ToolResult:
    parsed = FinishArgs.model_validate(args)
    ctx.state["finished"] = True
    ctx.state["status"] = parsed.status
    ctx.evidence.log_event("finish", {"status": parsed.status, "summary": parsed.summary})
    return ToolResult(ok=parsed.status == "success", data={"status": parsed.status, "summary": parsed.summary})
