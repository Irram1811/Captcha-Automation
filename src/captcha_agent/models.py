"""Validated data models used by the CAPTCHA agent."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SuccessRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["selector_text", "selector_visible", "js_flag", "token_field"]
    selector: str | None = None
    expr: str | None = None
    expected: Any = None

    @model_validator(mode="after")
    def validate_expression(self) -> "SuccessRule":
        if self.kind in {"selector_text", "selector_visible", "token_field"} and not self.selector:
            raise ValueError(f"{self.kind} success rules require selector")
        if self.kind == "js_flag" and not self.expr:
            raise ValueError("js_flag success rules require expr")
        return self


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    url: str
    expected_widget: Literal["checkbox", "slider", "image_grid", "none"]
    success: SuccessRule


class Detection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    widget: Literal["checkbox", "slider", "image_grid", "none", "unknown"]
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    data: Any = None
    error: str | None = None
    screenshot_path: str | None = None


class RunReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    target_id: str
    mode: str
    detected: Detection | None = None
    attempted_tool: str | None = None
    success: bool
    widget_mismatch: bool = False
    reason: str | None = None
    steps: int = Field(ge=0)
    duration_s: float = Field(ge=0)
    artifacts: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
