"""Run artifacts and event recording."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class EvidenceRecorder:
    """Write screenshots and structured events for one agent run."""

    def __init__(self, run_dir: str | Path, run_id: str, page: Any | None = None):
        self.run_dir = Path(run_dir) / run_id
        self.screenshot_dir = self.run_dir / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.run_dir / "events.jsonl"
        self.artifacts: list[str] = []
        self.page = page

    async def save_screenshot(self, name: str, page: Any | None = None) -> Path:
        """Save a full-page screenshot and register it as an artifact."""
        screenshot_page = page or self.page
        if screenshot_page is None:
            raise RuntimeError("EvidenceRecorder.page must be set before taking a screenshot")
        filename = name if name.endswith(".png") else f"{name}.png"
        path = self.screenshot_dir / filename
        await screenshot_page.screenshot(path=str(path), full_page=True)
        return self.attach_artifact(path)

    def log_event(self, event_type: str, payload: dict[str, Any] | None = None) -> Path:
        """Append one timestamped event to ``events.jsonl``."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "payload": payload or {},
        }
        with self.events_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, default=str) + "\n")
        return self.events_path

    def attach_artifact(self, path: str | Path) -> Path:
        """Register and return an artifact path."""
        artifact = Path(path)
        if artifact not in self.artifacts:
            self.artifacts.append(str(artifact))
        return artifact
