"""
Backend factory.

Imports are deliberately deferred until a backend is actually chosen: the local
backend pulls in torch, faster-whisper and Playwright, and someone running the
attendee backend should not need any of them installed.
"""

import config

from .base import MeetingBackend


def get_backend(name: str = None) -> MeetingBackend:
    """Build the configured backend. Raises config.ConfigError if unusable."""
    name = name or config.resolve_backend()

    if name == config.LOCAL:
        from .local import LocalBackend

        return LocalBackend()

    if name == config.ATTENDEE:
        from .attendee import AttendeeBackend

        return AttendeeBackend()

    raise config.ConfigError(f"Unknown backend {name!r}")


__all__ = ["MeetingBackend", "get_backend"]
