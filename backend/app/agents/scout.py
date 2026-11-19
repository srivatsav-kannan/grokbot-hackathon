"""Scout. Person C (@heruirayli) owns this file.

Rules (do not weaken these):
- Public pages only. Scout reads Craigslist SF Bay search result pages
  (`/search/bia`, `/search/sya`, `/search/fua`), which robots.txt allows.
- At most MAX_PAGES_PER_RUN network fetches per call, then stop.
- No sign-in, posting, messaging, replying, or account creation. No cookies are kept.
- Cache fetched pages on disk (backend/data/scout_cache/, gitignored) and reuse
  them for CACHE_TTL_SECONDS instead of refetching. Listings already stored are
  skipped by id in the service layer.
- On any CAPTCHA or block, raise ScoutStopped and report. Do not solve, evade,
  retry, or rotate around it.
- Live fetching is off unless SCOUT_LIVE=1, so tests and local runs never hit
  the network by accident. With it off, scout_run returns no new listings.

Stored fields: title, price, neighborhood, one image URL, category, and the
public source URL. No seller names, emails, or phone numbers are stored; titles
are scrubbed of anything that looks like an email or phone number.

Keep the signature of scout_run and ScoutStopped. The service layer stores the
returned listings and runs appraise and inspect before a row is readable.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx

from backend.app.repository import ListingRecord
from backend.app.schemas import ScoutReport

MAX_PAGES_PER_RUN = 3
MAX_LISTINGS_PER_CATEGORY = 8
REQUEST_TIMEOUT_SECONDS = 20.0
DELAY_BETWEEN_REQUESTS_SECONDS = 2.0
CACHE_TTL_SECONDS = 60 * 60
USER_AGENT = "FairlotScout/0.1 (Berkeley x Stanford Grok Bot Hackathon demo; reads public search pages only)"

SEARCH_BASE = "https://sfbay.craigslist.org/search/"
CATEGORY_CODES: dict[str, str] = {
    "bikes": "bia",
    "computers": "sya",
    "furniture": "fua",
}
PLACEHOLDERS: dict[str, str] = {
    "bikes": "/placeholders/bike.svg",
    "computers": "/placeholders/computer.svg",
    "furniture": "/placeholders/furniture.svg",
}
ALLOWED_HOSTS = ("craigslist.org",)
CHALLENGE_MARKERS = ("h-captcha", "hcaptcha.com/1/api", "g-recaptcha", "cf-challenge", "captcha-container")

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "scout_cache"


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


@dataclass
class ParsedItem:
    title: str
    price: int
    neighborhood: str
    url: str
    image: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


def response_is_challenge(status_code: int) -> str | None:
    """Classify a fetch response. None means it is safe to read as a public page.

    401, 403, 429, and 503 are treated as a block. There is no retry and no workaround.
    """

    if status_code in (401, 403, 429, 503):
        return "blocked"
    return None


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


def _http_get(url: str) -> httpx.Response:
    """One plain GET. Patched in tests so they never touch the network."""

    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        timeout=REQUEST_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        return client.get(url)


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _fetch(url: str) -> str:
    """Fetch a public page or raise ScoutStopped. Never retries."""

    try:
        response = _http_get(url)
    except httpx.HTTPError as exc:
        raise ScoutStopped("other", f"Could not reach the page ({type(exc).__name__}). Scout stopped.") from exc
    if response_is_challenge(response.status_code):
        raise ScoutStopped(
            "blocked",
            f"The site answered HTTP {response.status_code}. Scout stopped and will not retry.",
        )
    host = response.url.host or ""
    if not any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_HOSTS):
        raise ScoutStopped("other", "The page redirected off the public site. Scout stopped.")
    if response.status_code != 200:
        raise ScoutStopped("other", f"The site answered HTTP {response.status_code}. Scout stopped.")
    body = response.text
    lowered = body.lower()
    if any(marker in lowered for marker in CHALLENGE_MARKERS):
        raise ScoutStopped("captcha", "The page showed a CAPTCHA. Scout stopped and did not try to solve it.")
    return body


_LI_RE = re.compile(r'<li class="cl-static-search-result"[^>]*>(.*?)</li>', re.S)
_HREF_RE = re.compile(r'<a href="([^"]+)"')
_TITLE_RE = re.compile(r'<div class="title">(.*?)</div>', re.S)
_PRICE_RE = re.compile(r'<div class="price">(.*?)</div>', re.S)
_LOCATION_RE = re.compile(r'<div class="location">(.*?)</div>', re.S)
_LD_RE = re.compile(r'<script type="application/ld\+json" id="ld_searchpage_results"\s*>(.*?)</script>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")


def _text(fragment: str) -> str:
    return " ".join(html.unescape(_TAG_RE.sub(" ", fragment)).split())


def _scrub(text: str) -> str:
    text = _EMAIL_RE.sub("", text)
    text = _PHONE_RE.sub("", text)
    return " ".join(text.split()).strip(" -,")


def _price(raw: str) -> int | None:
    digits = re.sub(r"[^\d.]", "", raw)
    if not digits:
        return None
    try:
        value = int(float(digits))
    except ValueError:
        return None
    return value if value > 0 else None


def _images_by_title(body: str) -> dict[str, str]:
    match = _LD_RE.search(body)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return {}
    images: dict[str, str] = {}
    for element in data.get("itemListElement", []) if isinstance(data, dict) else []:
        item = element.get("item", {}) if isinstance(element, dict) else {}
        name = _text(str(item.get("name", "")))
        pics = item.get("image") or []
        if isinstance(pics, str):
            pics = [pics]
        if name and pics and isinstance(pics[0], str) and pics[0].startswith("https://images.craigslist.org/"):
            images.setdefault(name, pics[0])
    return images


def parse_search_page(body: str) -> list[ParsedItem]:
    """Parse the no-JS result list of a public search page. Items without a price are skipped."""

    images = _images_by_title(body)
    items: list[ParsedItem] = []
    for block in _LI_RE.findall(body):
        href = _HREF_RE.search(block)
        title_match = _TITLE_RE.search(block)
        price_match = _PRICE_RE.search(block)
        if not href or not title_match or not price_match:
            continue
        price = _price(_text(price_match.group(1)))
        if price is None:
            continue
        raw_title = _text(title_match.group(1))
        title = _scrub(raw_title)
        url = html.unescape(href.group(1))
        if not title or not url.startswith("https://"):
            continue
        location_match = _LOCATION_RE.search(block)
        neighborhood = _scrub(_text(location_match.group(1))) if location_match else ""
        if neighborhood.islower():
            neighborhood = neighborhood.title()
        items.append(
            ParsedItem(
                title=title[:120],
                price=price,
                neighborhood=neighborhood or "SF Bay Area",
                url=url,
                image=images.get(raw_title),
            )
        )
    return items


def _listing_id(url: str) -> str:
    return "lst_cl_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def _to_record(item: ParsedItem, category: str, posted_at: str) -> ListingRecord:
    return ListingRecord(
        id=_listing_id(item.url),
        category=category,
        title=item.title,
        description="Found on a public Craigslist SF Bay search page. Open the source link for the full post.",
        price=item.price,
        photos=[item.image] if item.image else [PLACEHOLDERS[category]],
        neighborhood=item.neighborhood,
        source_url=item.url,
        posted_at=posted_at,
        origin="scout",
    )


def scout_run(categories: list[str]) -> ScoutRunResult:
    """Read at most MAX_PAGES_PER_RUN public search pages and return new listing records.

    Raises ScoutStopped on a block before anything was collected. If a block
    happens after some pages were read, returns what was collected with stopped=True.
    """

    if not live_enabled():
        return ScoutRunResult(listings=[])

    posted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    listings: list[ListingRecord] = []
    fetched = 0
    for category in categories:
        code = CATEGORY_CODES.get(category)
        if code is None:
            continue
        url = SEARCH_BASE + code
        body = _read_cache(url)
        if body is None:
            if fetched >= MAX_PAGES_PER_RUN:
                break
            if fetched:
                _sleep(DELAY_BETWEEN_REQUESTS_SECONDS)
            fetched += 1
            try:
                body = _fetch(url)
            except ScoutStopped as exc:
                if not listings:
                    raise
                return ScoutRunResult(
                    listings=listings,
                    stopped=True,
                    report=ScoutReport(reason=exc.reason, message=exc.message),  # type: ignore[arg-type]
                )
            _write_cache(url, body)
        items = parse_search_page(body)[:MAX_LISTINGS_PER_CATEGORY]
        listings.extend(_to_record(item, category, posted_at) for item in items)
    return ScoutRunResult(listings=listings)
