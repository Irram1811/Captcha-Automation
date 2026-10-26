"""Open a fixture and produce screenshot, event, and trace artifacts."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import argparse
import asyncio
from datetime import datetime, timezone

from captcha_agent.browser import BrowserSession
from captcha_agent.config import load_config
from captcha_agent.evidence import EvidenceRecorder


async def smoke(url: str, run_dir: str | Path) -> Path:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_smoke")
    settings = load_config().settings.model_copy(update={"run_dir": str(run_dir)})
    evidence = EvidenceRecorder(run_dir, run_id)
    async with BrowserSession(run_id, settings, evidence) as session:
        assert session.page is not None
        await session.page.goto(url)
        await evidence.save_screenshot("initial")
        evidence.log_event("page_opened", {"url": session.page.url})
    return evidence.run_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765/none.html")
    parser.add_argument("--run-dir", default="runs")
    args = parser.parse_args()
    print(asyncio.run(smoke(args.url, args.run_dir)))


if __name__ == "__main__":
    main()
