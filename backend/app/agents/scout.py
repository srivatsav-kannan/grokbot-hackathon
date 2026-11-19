"""Scout. Person C (@heruirayli) owns this file.

Rules (do not weaken these when a fetcher is added):
- Public pages only.
- At most MAX_PAGES_PER_RUN pages per call, then stop.
- No sign-in, posting, messaging, or account creation.
- Cache what you already stored and reuse it instead of refetching.
- On any CAPTCHA or block, stop and report. Do not solve, evade, or rotate around it.
- This scaffold does not request Craigslist. scout_run returns no new listings.

Replace the body of scout_run. Keep the signature and ScoutStopped.
The service layer stores returned listings, then calls appraise and inspect.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.repository import ListingRecord
from backend.app.schemas import ScoutReport

MAX_PAGES_PER_RUN = 3


class ScoutStopped(Exception):
    """Raised when a page returns a challenge or a block. Callers report and stop."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass
class ScoutRunResult:
    listings: list[ListingRecord]
    stopped: bool = False
    report: ScoutReport | None = None


def response_is_challenge(status_code: int) -> str | None:
    """Classify a future fetch response. None means it is safe to read as a public page.

    401, 403, 429, and 503 are treated as a block. There is no retry and no workaround.
    """

    if status_code in (401, 403, 429, 503):
        return "blocked"
    return None


def scout_run(categories: list[str]) -> ScoutRunResult:
    _ = categories[:MAX_PAGES_PER_RUN]
    return ScoutRunResult(listings=[])
