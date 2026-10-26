"""Shared execution context for agent tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import Page

from ..browser import BrowserSession
from ..config import AppConfig
from ..evidence import EvidenceRecorder
from ..models import Detection, Target


@dataclass
class RunContext:
    session: BrowserSession
    config: AppConfig
    evidence: EvidenceRecorder
    target: Target | None = None
    detection: Detection | None = None
    state: dict[str, Any] = field(default_factory=dict)

    @property
    def page(self) -> Page:
        if self.session.page is None:
            raise RuntimeError("Browser session has no active page")
        return self.session.page
