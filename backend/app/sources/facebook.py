"""Facebook Marketplace is not fetched.

Public marketplace URLs redirect to a login page. Scout does not sign in,
create an account, or send messages.
"""

from __future__ import annotations

from backend.app.sources.fetch import PageFetcher

NAME = "facebook"
SKIP_MESSAGE = "Facebook Marketplace requires sign-in. Scout does not sign in, post, or create accounts."


def collect(categories: list[str], fetcher: PageFetcher, posted_at: str):
    from backend.app.sources.aggregate import SourceBatch

    del categories, fetcher, posted_at
    return SourceBatch([], skipped=True, reason="login_required", message=SKIP_MESSAGE)
