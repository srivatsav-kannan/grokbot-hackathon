"""Scout. Person C (@heruirayli) owns this file.

Rules (do not weaken these):
- Public pages only. Craigslist SF Bay search pages, plus other marketplaces
  that answer without an account (eBay local pickup near San Francisco,
  OfferUp, Mercari). Facebook Marketplace and Nextdoor need sign-in and are
  not fetched.
- At most MAX_PAGES_PER_RUN network fetches per source per call, then that
  source stops. A cached page does not count.
- No sign-in, posting, messaging, replying, or account creation. No cookies are kept.
- Cache fetched pages on disk (backend/data/scout_cache/, gitignored) and reuse
  them for CACHE_TTL_SECONDS instead of refetching. Listings already stored are
  skipped by id in the service layer. Within a run, the same source and
  external id are kept once.
- On any CAPTCHA or block, that source stops and is reported. Do not solve,
  evade, retry, or rotate around it. Other sources still run. If nothing was
  collected, scout_run raises ScoutStopped as before.
- Live fetching is off unless SCOUT_LIVE=1, so tests and local runs never hit
  the network by accident. With it off, scout_run and scout_query return nothing.
- scout_query(query, category=None) searches each enabled source once for that
  text. Sources run together. Each source has its own timeout, and the call
  returns within QUERY_DEADLINE_SECONDS (15s). A block stops only that source.
- Optional EBAY_APP_ID selects eBay's public Finding API instead of the search
  page. It is read from the environment only.

Stored fields: title, price, neighborhood, image URLs, category, source
marketplace, external id, and the public source URL. No seller names, emails,
or phone numbers are stored; titles are scrubbed of anything that looks like
an email or phone number.

Keep the signature of scout_run and ScoutStopped. The service layer stores the
returned listings and runs appraise and inspect before a row is readable.
Returned listings are ListingRecords with `source` and `source_url` set.
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from threading import Thread

import httpx

from backend.app.repository import ListingRecord
from backend.app.schemas import ScoutReport
from backend.app.sources.aggregate import QUERY_SOURCES, SourceReport, collect_all
from backend.app.sources.craigslist import (
    ALLOWED_HOSTS,
    CATEGORY_CODES,
    SEARCH_BASE,
    ParsedItem,
    parse_search_page,
)
from backend.app.sources.errors import ScoutStopped
from backend.app.sources.fetch import CHALLENGE_MARKERS, PageFetcher, response_is_challenge
from backend.app.sources.listing import (
    MAX_LISTINGS_PER_CATEGORY,
    PLACEHOLDERS,
    ScoutedListing,
    category_from_text,
    dedupe,
)

MAX_PAGES_PER_RUN = 3
REQUEST_TIMEOUT_SECONDS = 20.0
DELAY_BETWEEN_REQUESTS_SECONDS = 2.0
CACHE_TTL_SECONDS = 60 * 60
# On-demand search: one page per source, in parallel, bounded by these clocks.
QUERY_DEADLINE_SECONDS = 15.0
QUERY_SOURCE_TIMEOUT_SECONDS = 8.0
USER_AGENT = "FairlotScout/0.1 (Berkeley x Stanford Grok Bot Hackathon demo; reads public search pages only)"

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "scout_cache"

__all__ = [
    "ALLOWED_HOSTS",
    "CACHE_TTL_SECONDS",
    "CATEGORY_CODES",
    "CHALLENGE_MARKERS",
    "DELAY_BETWEEN_REQUESTS_SECONDS",
    "MAX_LISTINGS_PER_CATEGORY",
    "MAX_PAGES_PER_RUN",
    "PLACEHOLDERS",
    "ParsedItem",
    "REQUEST_TIMEOUT_SECONDS",
    "SEARCH_BASE",
    "ScoutRunResult",
    "ScoutStopped",
    "ScoutedListing",
    "SourceReport",
    "USER_AGENT",
    "live_enabled",
    "parse_search_page",
    "response_is_challenge",
    "QUERY_DEADLINE_SECONDS",
    "QUERY_SOURCE_TIMEOUT_SECONDS",
    "scout_query",
    "scout_run",
]


@dataclass
class ScoutRunResult:
    listings: list[ListingRecord]
    stopped: bool = False
    report: ScoutReport | None = None
    sources: list[SourceReport] = field(default_factory=list)


def live_enabled() -> bool:
    return os.environ.get("SCOUT_LIVE", "").strip().lower() in ("1", "true", "yes", "on")


def _cache_dir() -> Path:
    override = os.environ.get("SCOUT_CACHE_DIR", "").strip()
    return Path(override) if override else DEFAULT_CACHE_DIR


def _cache_path(url: str) -> Path:
    return _cache_dir() / (hashlib.sha256(url.encode("utf-8")).hexdigest()[:16] + ".html")


def _read_cache(url: str) -> str | None:
    path = _cache_path(url)
    try:
        if time.time() - path.stat().st_mtime > CACHE_TTL_SECONDS:
            return None
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _write_cache(url: str, body: str) -> None:
    path = _cache_path(url)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    except OSError:
        pass


def _http_get_timeout(url: str, timeout: float) -> httpx.Response:
    """One plain GET. Patched in tests so they never touch the network."""

    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"},
        timeout=httpx.Timeout(timeout),
        follow_redirects=True,
    ) as client:
        return client.get(url)


def _http_get(url: str) -> httpx.Response:
    return _http_get_timeout(url, REQUEST_TIMEOUT_SECONDS)


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _prefer_stop(reports: list[SourceReport]) -> SourceReport:
    rank = {"captcha": 0, "blocked": 1, "other": 2}
    return min(reports, key=lambda item: rank.get(item.reason or "other", 9))


def _stop_message(reports: list[SourceReport]) -> str:
    parts = [item.message for item in reports if item.message]
    return " ".join(parts) if parts else "A source stopped. Scout did not retry it."


def scout_run(categories: list[str]) -> ScoutRunResult:
    """Read at most MAX_PAGES_PER_RUN public pages per source and return listing records.

    Raises ScoutStopped when a block happens and nothing was collected. If a
    source is blocked after another source already returned listings, those
    listings are returned with stopped=True.
    """

    if not live_enabled():
        return ScoutRunResult(listings=[])

    posted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fetcher = PageFetcher(
        get=_http_get,
        sleep=_sleep,
        read_cache=_read_cache,
        write_cache=_write_cache,
        max_pages=MAX_PAGES_PER_RUN,
        delay=DELAY_BETWEEN_REQUESTS_SECONDS,
    )
    listings, reports = collect_all(categories, fetcher, posted_at)
    stopped_reports = [item for item in reports if item.stopped]
    if stopped_reports and not listings:
        primary = _prefer_stop(stopped_reports)
        raise ScoutStopped(primary.reason or "other", _stop_message(stopped_reports))
    report = None
    if stopped_reports:
        primary = _prefer_stop(stopped_reports)
        report = ScoutReport(reason=primary.reason or "other", message=_stop_message(stopped_reports))  # type: ignore[arg-type]
    return ScoutRunResult(
        listings=listings,
        stopped=bool(stopped_reports),
        report=report,
        sources=reports,
    )


def _query_sources(query: str, category: str | None, posted_at: str) -> list[ScoutedListing]:
    """Fetch enabled sources together. A source still running at the deadline is dropped."""

    found: Queue[list[ScoutedListing]] = Queue()
    timeout = QUERY_SOURCE_TIMEOUT_SECONDS

    def run(module) -> None:
        def get(url: str) -> httpx.Response:
            return _http_get_timeout(url, timeout)

        fetcher = PageFetcher(
            get=get,
            sleep=_sleep,
            read_cache=_read_cache,
            write_cache=_write_cache,
            max_pages=MAX_PAGES_PER_RUN,
            delay=DELAY_BETWEEN_REQUESTS_SECONDS,
        )
        try:
            batch = module.collect_query(query, category, fetcher, posted_at)
        except Exception:
            batch = None
        found.put([] if batch is None else list(batch.listings))

    threads = [Thread(target=run, args=(module,), daemon=True) for module in QUERY_SOURCES]
    for thread in threads:
        thread.start()
    combined: list[ScoutedListing] = []
    deadline = time.monotonic() + QUERY_DEADLINE_SECONDS
    received = 0
    while received < len(threads) and time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            combined.extend(found.get(timeout=remaining))
        except Empty:
            break
        received += 1
    return dedupe(combined)


def scout_query(query: str, category: str | None = None) -> list[ScoutedListing]:
    """Search enabled public sources for free text and return normalized listings.

    `category` is `bikes`, `computers`, or `furniture`. When it is omitted, a
    category named in the query is used; otherwise each title is classified
    and titles that match none of the three are dropped.

    Facebook Marketplace and Nextdoor are not queried. They require sign-in.
    One page is fetched per source, under the same page cap, cache, and
    block rules as scout_run. Sources run at the same time. Each source times
    out on its own, and this returns within QUERY_DEADLINE_SECONDS. A blocked
    source contributes nothing and is not retried. Live fetching is off unless
    SCOUT_LIVE=1.
    """

    if not live_enabled():
        return []
    text = " ".join(query.split())
    if not text:
        return []
    if category is not None and category not in CATEGORY_CODES:
        return []
    scoped = category or category_from_text(text)
    posted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return _query_sources(text, scoped, posted_at)
