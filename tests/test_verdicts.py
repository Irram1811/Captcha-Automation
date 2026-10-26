import pytest

from captcha_agent.models import Detection, RunReport
from captcha_agent.report import verdict
from captcha_agent.vision.tile_classifier import FakeTileClassifier


def _image_grid_report(*, success: bool, reason: str | None, details: dict | None = None) -> RunReport:
    return RunReport(
        run_id="verdict-test",
        target_id="local_imagegrid",
        mode="deterministic",
        detected=Detection(widget="image_grid", confidence=0.97),
        attempted_tool="solve_image_grid",
        success=success,
        reason=reason,
        steps=1,
        duration_s=0.1,
        details=details or {},
    )


def test_missing_classifier_is_skipped():
    report = _image_grid_report(
        success=False,
        reason="ANTHROPIC_API_KEY is missing or no tile classifier was injected",
        details={"verdict": "SKIPPED"},
    )
    assert verdict(report) == "SKIPPED"


def test_missing_api_key_reason_is_skipped_without_detail_override():
    report = _image_grid_report(
        success=False,
        reason="ANTHROPIC_API_KEY is missing or no tile classifier was injected",
    )
    assert verdict(report) == "SKIPPED"


@pytest.mark.asyncio
async def test_fake_classifier_success_is_pass():
    classifier = FakeTileClassifier({0: True})
    tile = await classifier.matches_at(0, "circle", b"fixture-tile")
    assert tile.match is True
    assert verdict(_image_grid_report(success=True, reason=None)) == "PASS"


@pytest.mark.asyncio
async def test_fake_classifier_failed_verification_is_fail():
    classifier = FakeTileClassifier({0: False})
    tile = await classifier.matches_at(0, "circle", b"fixture-tile")
    assert tile.match is False
    report = _image_grid_report(success=False, reason="Image-grid verification failed")
    assert verdict(report) == "FAIL"
