"""Craigslist SF Bay public search pages. No sign-in, no posting."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from urllib.parse import urlencode, urlparse

from backend.app.sources.errors import PageLimit, ScoutStopped
from backend.app.sources.fetch import PageFetcher
from backend.app.sources.listing import (
    MAX_LISTINGS_PER_CATEGORY,
    ScoutedListing,
    build_listing,
    resolve_category,
    scrub,
)

NAME = "craigslist"
SEARCH_BASE = "https://sfbay.craigslist.org/search/"
ALLOWED_HOSTS = ("craigslist.org",)
CATEGORY_CODES: dict[str, str] = {
    "bikes": "bia",
    "computers": "sya",
    "furniture": "fua",
}
DESCRIPTION = "Found on a public Craigslist SF Bay search page. Open the source link for the full post."

_LI_RE = re.compile(r'<li class="cl-static-search-result"[^>]*>(.*?)</li>', re.S)
_HREF_RE = re.compile(r'<a href="([^"]+)"')
_TITLE_RE = re.compile(r'<div class="title">(.*?)</div>', re.S)
_PRICE_RE = re.compile(r'<div class="price">(.*?)</div>', re.S)
_LOCATION_RE = re.compile(r'<div class="location">(.*?)</div>', re.S)
_LD_RE = re.compile(r'<script type="application/ld\+json" id="ld_searchpage_results"\s*>(.*?)</script>', re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_POST_ID_RE = re.compile(r"/(\d+)\.html")


@dataclass
class ParsedItem:
    title: str
    price: int
    neighborhood: str
    url: str
    image: str | None = None
    extra: dict[str, str] = field(default_factory=dict)
    images: list[str] = field(default_factory=list)


def _text(fragment: str) -> str:
    return " ".join(html.unescape(_TAG_RE.sub(" ", fragment)).split())


def _images_by_title(body: str) -> dict[str, list[str]]:
    match = _LD_RE.search(body)
    if not match:
        return {}
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return {}
    images: dict[str, list[str]] = {}
    for element in data.get("itemListElement", []) if isinstance(data, dict) else []:
        item = element.get("item", {}) if isinstance(element, dict) else {}
        name = _text(str(item.get("name", "")))
        pics = item.get("image") or []
        if isinstance(pics, str):
            pics = [pics]
        kept = [
            pic
            for pic in pics
            if isinstance(pic, str) and pic.startswith("https://images.craigslist.org/")
        ][:4]
        if name and kept:
            images.setdefault(name, kept)
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
        price_text = _text(price_match.group(1))
        digits = re.sub(r"[^\d.]", "", price_text)
        if not digits:
            continue
        try:
            price = int(float(digits))
        except ValueError:
            continue
        if price <= 0:
            continue
        raw_title = _text(title_match.group(1))
        title = scrub(raw_title)
        url = html.unescape(href.group(1))
        if not title or not url.startswith("https://"):
            continue
        location_match = _LOCATION_RE.search(block)
        neighborhood = scrub(_text(location_match.group(1))) if location_match else ""
        if neighborhood.islower():
            neighborhood = neighborhood.title()
        pics = images.get(raw_title, [])
        items.append(
            ParsedItem(
                title=title[:120],
                price=price,
                neighborhood=neighborhood or "SF Bay Area",
                url=url,
                image=pics[0] if pics else None,
                images=pics,
            )
        )
    return items


def query_url(query: str, category: str | None) -> str:
    """Public SF Bay search. `query` is the parameter the live site honors."""

    params: dict[str, str] = {"query": query}
    if category in CATEGORY_CODES:
        params["cat"] = CATEGORY_CODES[category]
    return "https://www.craigslist.org/search/area/sfbay?" + urlencode(params)


def _external_id(url: str) -> str:
    bare = url.split("?", 1)[0]
    match = _POST_ID_RE.search(bare)
    if match:
        return match.group(1)
    parts = urlparse(bare).path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == "view" and parts[-1]:
        return parts[-1]
    return bare


def listings_from_page(body: str, category: str | None, posted_at: str) -> list[ScoutedListing]:
    found: list[ScoutedListing] = []
    for item in parse_search_page(body)[:MAX_LISTINGS_PER_CATEGORY]:
        resolved = resolve_category(category, item.title)
        if resolved is None:
            continue
        listing = build_listing(
            source=NAME,
            external_id=_external_id(item.url),
            category=resolved,
            title=item.title,
            price=item.price,
            neighborhood=item.neighborhood,
            source_url=item.url,
            photos=item.images,
            posted_at=posted_at,
            description=DESCRIPTION,
        )
        if listing is not None:
            found.append(listing)
    return found


def collect(categories: list[str], fetcher: PageFetcher, posted_at: str):
    from backend.app.sources.aggregate import SourceBatch

    found: list[ScoutedListing] = []
    for category in categories:
        code = CATEGORY_CODES.get(category)
        if code is None:
            continue
        url = SEARCH_BASE + code
        try:
            body = fetcher.fetch(NAME, url, ALLOWED_HOSTS)
        except PageLimit:
            break
        except ScoutStopped as exc:
            return SourceBatch(found, stopped=True, reason=exc.reason, message=exc.message)
        found.extend(listings_from_page(body, category, posted_at))
    return SourceBatch(found)


def collect_query(query: str, category: str | None, fetcher: PageFetcher, posted_at: str):
    """One public search page for the free-text query. A block stops this source only."""

    from backend.app.sources.aggregate import SourceBatch

    try:
        body = fetcher.fetch(NAME, query_url(query, category), ALLOWED_HOSTS)
    except PageLimit:
        return SourceBatch()
    except ScoutStopped as exc:
        return SourceBatch([], stopped=True, reason=exc.reason, message=exc.message)
    return SourceBatch(listings_from_page(body, category, posted_at))
