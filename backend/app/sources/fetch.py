"""Polite public GET helper. One source stops on a block; it does not retry."""

from __future__ import annotations

import httpx

from backend.app.sources.errors import PageLimit, ScoutStopped
from backend.app.sources.listing import DISPLAY_NAMES

CHALLENGE_MARKERS = (
    "h-captcha",
    "hcaptcha.com/1/api",
    "g-recaptcha",
    "cf-challenge",
    "captcha-container",
)


def response_is_challenge(status_code: int) -> str | None:
    """Classify a fetch response. None means it is safe to read as a public page.

    401, 403, 429, and 503 are treated as a block. There is no retry and no workaround.
    """

    if status_code in (401, 403, 429, 503):
        return "blocked"
    return None


def host_allowed(host: str, allowed_hosts: tuple[str, ...]) -> bool:
    return any(host == allowed or host.endswith("." + allowed) for allowed in allowed_hosts)


class PageFetcher:
    """Cache, delay, and a per-source page cap shared by every marketplace."""

    def __init__(
        self,
        get,
        sleep,
        read_cache,
        write_cache,
        max_pages: int,
        delay: float,
    ) -> None:
        self._get = get
        self._sleep = sleep
        self._read_cache = read_cache
        self._write_cache = write_cache
        self._max_pages = max_pages
        self._delay = delay
        self.counts: dict[str, int] = {}
        self._network = 0

    def fetch(self, source: str, url: str, allowed_hosts: tuple[str, ...]) -> str:
        cached = self._read_cache(url)
        if cached is not None:
            self._reject_challenge_body(cached, source)
            return cached
        if self.counts.get(source, 0) >= self._max_pages:
            raise PageLimit()
        if self._network:
            self._sleep(self._delay)
        self.counts[source] = self.counts.get(source, 0) + 1
        self._network += 1
        try:
            response = self._get(url)
        except httpx.HTTPError as exc:
            raise ScoutStopped(
                "other",
                f"{_label(source)} could not be reached ({type(exc).__name__}). Scout stopped that source.",
            ) from exc
        if response_is_challenge(response.status_code):
            raise ScoutStopped(
                "blocked",
                f"{_label(source)} answered HTTP {response.status_code}. Scout stopped that source and will not retry.",
            )
        host = response.url.host or ""
        if not host_allowed(host, allowed_hosts):
            raise ScoutStopped(
                "other",
                f"{_label(source)} redirected off the public site. Scout stopped that source.",
            )
        if response.status_code != 200:
            raise ScoutStopped(
                "other",
                f"{_label(source)} answered HTTP {response.status_code}. Scout stopped that source.",
            )
        body = response.text
        self._reject_challenge_body(body, source)
        self._write_cache(url, body)
        return body

    def _reject_challenge_body(self, body: str, source: str) -> None:
        lowered = body.lower()
        if any(marker in lowered for marker in CHALLENGE_MARKERS):
            raise ScoutStopped(
                "captcha",
                f"{_label(source)} showed a CAPTCHA. Scout stopped that source and did not try to solve it.",
            )


def _label(source: str) -> str:
    return DISPLAY_NAMES.get(source, source)
