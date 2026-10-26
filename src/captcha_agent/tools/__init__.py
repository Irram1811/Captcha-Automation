"""Tool registry and common tool metadata."""

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .click_checkbox import ClickCheckboxArgs, tool as click_checkbox
from .context import RunContext
from .detect_widget import DetectWidgetArgs, tool as detect_widget
from .finish import FinishArgs, tool as finish
from .observe import ObserveArgs, tool as observe
from .open_target import OpenTargetArgs, tool as open_target
from .solve_slider import SolveSliderArgs, tool as solve_slider
from .solve_image_grid import SolveImageGridArgs, tool as solve_image_grid
from .verify_result import VerifyResultArgs, tool as verify_result

ToolHandler = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    args_model: type
    handler: ToolHandler

    @property
    def json_schema(self) -> dict[str, Any]:
        return self.args_model.model_json_schema()


TOOL_REGISTRY: dict[str, ToolDefinition] = {
    "open_target": ToolDefinition("open_target", "Validate and open an allowlisted target.", OpenTargetArgs, open_target),
    "observe": ToolDefinition("observe", "Capture a screenshot and compact DOM summary.", ObserveArgs, observe),
    "detect_widget": ToolDefinition("detect_widget", "Detect checkbox, slider, image_grid, none, or unknown deterministically.", DetectWidgetArgs, detect_widget),
    "click_checkbox": ToolDefinition("click_checkbox", "Click and wait for a checkbox CAPTCHA to verify.", ClickCheckboxArgs, click_checkbox),
    "solve_slider": ToolDefinition("solve_slider", "Visually locate and drag a slider puzzle piece.", SolveSliderArgs, solve_slider),
    "solve_image_grid": ToolDefinition("solve_image_grid", "Classify and verify tiles in the local image-grid fixture.", SolveImageGridArgs, solve_image_grid),
    "verify_result": ToolDefinition("verify_result", "Evaluate the configured success rule independently.", VerifyResultArgs, verify_result),
    "finish": ToolDefinition("finish", "Record the terminal agent conclusion.", FinishArgs, finish),
}


def tool_schemas() -> list[dict[str, Any]]:
    return [{"name": item.name, "description": item.description, "input_schema": item.json_schema} for item in TOOL_REGISTRY.values()]


__all__ = ["RunContext", "TOOL_REGISTRY", "ToolDefinition", "tool_schemas"]
