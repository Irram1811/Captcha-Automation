from pathlib import Path

import pytest

from captcha_agent.allowlist import AllowlistError, assert_allowed
from captcha_agent.config import load_config


@pytest.fixture()
def config():
    return load_config(Path(__file__).parents[1] / "config")


def test_allows_configured_authority(config):
    assert_allowed("http://127.0.0.1:8765/checkbox.html", config)


def test_allows_other_path_on_configured_authority(config):
    assert_allowed("http://127.0.0.1:8765/not-a-target.html", config)


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8765/checkbox.html",
        "http://localhost:8765/checkbox.html",
        "http://127.0.0.1:8766/checkbox.html",
        "http://127.0.0.2:8765/checkbox.html",
    ],
)
def test_rejects_unconfigured_scheme_host_or_port(config, url):
    with pytest.raises(AllowlistError):
        assert_allowed(url, config)
