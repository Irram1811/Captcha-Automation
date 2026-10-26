"""Domain-specific errors exposed by the agent."""


class AllowlistError(ValueError):
    """A URL is outside the configured scheme/host/port allowlist."""


class WidgetNotFound(RuntimeError):
    """The expected widget or its required controls were not found."""


class VerificationFailed(RuntimeError):
    """The configured success rule was evaluated but did not pass."""
