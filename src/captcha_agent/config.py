"""Load and validate the agent's YAML configuration files."""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .models import Target


class Viewport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int = Field(gt=0)
    height: int = Field(gt=0)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    headless: bool = True
    viewport: Viewport
    step_timeout_ms: int = Field(gt=0)
    max_steps: int = Field(gt=0)
    max_slider_attempts: int = Field(default=3, gt=0)
    tile_classifier: Literal["anthropic", "fake"] = "anthropic"
    run_dir: str


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[Target]
    settings: Settings

    def target_by_id(self, target_id: str) -> Target:
        for target in self.targets:
            if target.id == target_id:
                return target
        raise KeyError(f"Unknown target: {target_id}")


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        value = yaml.safe_load(stream) or {}
    if not isinstance(value, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return value


def load_config(config_dir: str | Path | None = None) -> AppConfig:
    """Load ``targets.yaml`` and ``settings.yaml`` from a config directory."""
    root = Path(config_dir) if config_dir is not None else Path(__file__).resolve().parents[2] / "config"
    targets_data = _read_yaml(root / "targets.yaml")
    settings_data = _read_yaml(root / "settings.yaml")
    targets = targets_data.get("targets", targets_data)
    if not isinstance(targets, list):
        raise ValueError("targets.yaml must contain a 'targets' list")
    return AppConfig.model_validate({"targets": targets, "settings": settings_data})
