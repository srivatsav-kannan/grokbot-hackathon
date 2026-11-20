"""Errors Scout can raise without trying to get around a block."""

from __future__ import annotations


class ScoutStopped(Exception):
    """Raised when a page returns a challenge or a block. Callers report and stop."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


class PageLimit(Exception):
    """The source already used its fetch budget for this run."""
