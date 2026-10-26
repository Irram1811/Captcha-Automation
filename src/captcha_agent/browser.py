"""Playwright browser session management."""

from __future__ import annotations

import contextlib
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from .config import Settings
from .evidence import EvidenceRecorder


class BrowserSession:
    """Launch a traced Chromium context for one run."""

    def __init__(self, run_id: str, settings: Settings, evidence: EvidenceRecorder | None = None):
        self.run_id = run_id
        self.settings = settings
        self.evidence = evidence or EvidenceRecorder(settings.run_dir, run_id)
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.trace_path = self.evidence.run_dir / "trace.zip"
        self.tracing_started = False

    async def __aenter__(self) -> "BrowserSession":
        self.playwright = await async_playwright().start()
        try:
            self.browser = await self.playwright.chromium.launch(headless=self.settings.headless)
            self.context = await self.browser.new_context(
                viewport={"width": self.settings.viewport.width, "height": self.settings.viewport.height}
            )
            self.context.set_default_timeout(self.settings.step_timeout_ms)
            self.context.set_default_navigation_timeout(self.settings.step_timeout_ms)
            await self.context.tracing.start(screenshots=True, snapshots=True, sources=True)
            self.tracing_started = True
            self.page = await self.context.new_page()
            self.evidence.page = self.page
            return self
        except Exception:
            await self._close_resources()
            raise

    async def __aexit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        try:
            if self.context is not None and self.tracing_started:
                with contextlib.suppress(Exception):
                    await self.context.tracing.stop(path=str(self.trace_path))
                    self.evidence.attach_artifact(self.trace_path)
        finally:
            self.tracing_started = False
            await self._close_resources()

    async def _close_resources(self) -> None:
        if self.context is not None:
            with contextlib.suppress(Exception):
                await self.context.close()
            self.context = None
        if self.browser is not None:
            with contextlib.suppress(Exception):
                await self.browser.close()
            self.browser = None
        if self.playwright is not None:
            with contextlib.suppress(Exception):
                await self.playwright.stop()
            self.playwright = None
