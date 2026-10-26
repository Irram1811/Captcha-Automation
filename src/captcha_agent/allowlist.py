"""URL authority allowlist enforcement."""

from urllib.parse import urlsplit

from .config import AppConfig, load_config
from .errors import AllowlistError


def _authority(url: str) -> tuple[str, str, int | None]:
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.hostname:
        raise AllowlistError(f"Invalid URL: {url}")
    try:
        port = parsed.port
    except ValueError as exc:
        raise AllowlistError(f"Invalid URL port: {url}") from exc
    return parsed.scheme.lower(), parsed.hostname.lower(), port


def assert_allowed(url: str, config: AppConfig | None = None) -> None:
    """Raise :class:`AllowlistError` unless URL scheme/host/port is configured."""
    candidate = _authority(url)
    settings = config or load_config()
    allowed = {_authority(target.url) for target in settings.targets}
    if candidate not in allowed:
        raise AllowlistError(f"URL authority is not allowlisted: {url}")
