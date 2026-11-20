"""Nextdoor for-sale listings are not fetched.

The for-sale pages are not available without an account. Scout does not
sign in or create an account.
"""

from __future__ import annotations

from backend.app.sources.fetch import PageFetcher

NAME = "nextdoor"
SKIP_MESSAGE = "Nextdoor for-sale listings require sign-in. Scout does not sign in or create accounts."


def collect(categories: list[str], fetcher: PageFetcher, posted_at: str):
    from backend.app.sources.aggregate import SourceBatch

    del categories, fetcher, posted_at
    return SourceBatch([], skipped=True, reason="login_required", message=SKIP_MESSAGE)
