"""OfferUp public search pages.

The search HTML is readable without an account. OfferUp does not honor a
latitude and longitude from this network (it falls back to a default US
location), so listings are kept only when their own location is in the
SF Bay Area. A block stops this source. Scout does not sign in.
"""

from __future__ import annotations

import json
import re
from urllib.parse import urlencode

from backend.app.sources.errors import PageLimit, ScoutStopped
from backend.app.sources.fetch import PageFetcher
from backend.app.sources.listing import (
    MAX_LISTINGS_PER_CATEGORY,
    ScoutedListing,
    accept_place,
    build_listing,
    parse_price,
    resolve_category,
)

NAME = "offerup"
ALLOWED_HOSTS = ("offerup.com",)
QUERIES: dict[str, str] = {
    "bikes": "bicycle",
    "computers": "laptop",
    "furniture": "sofa",
}
DESCRIPTION = "Found on a public OfferUp search page. Open the source link for the full post."
_NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def search_url(keyword: str) -> str:
    params = {
        "q": keyword,
        "lat": "37.7749",
        "lon": "-122.4194",
        "radius": "50",
    }
    return "https://offerup.com/search?" + urlencode(params)


def parse_search_page(body: str) -> list[dict[str, object]]:
    match = _NEXT_RE.search(body)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return []
    page_props = data.get("props", {}).get("pageProps", {}) if isinstance(data, dict) else {}
    feed = page_props.get("searchFeedResponse", {}) if isinstance(page_props, dict) else {}
    tiles = feed.get("looseTiles", []) if isinstance(feed, dict) else []
    items: list[dict[str, object]] = []
    if not isinstance(tiles, list):
        return items
    for tile in tiles:
        listing = tile.get("listing") if isinstance(tile, dict) else None
        if not isinstance(listing, dict):
            continue
        external_id = listing.get("listingId")
        title = listing.get("title")
        if not isinstance(external_id, str) or not isinstance(title, str):
            continue
        price = parse_price(listing.get("price"))
        if price is None:
            continue
        image = listing.get("image")
        photo = image.get("url") if isinstance(image, dict) else None
        location = listing.get("locationName")
        items.append(
            {
                "external_id": external_id,
                "title": title,
                "price": price,
                "location": location if isinstance(location, str) else "",
                "url": f"https://offerup.com/item/detail/{external_id}",
                "photos": [photo] if isinstance(photo, str) else [],
            }
        )
    return items


def _to_listings(rows: list[dict[str, object]], category: str | None, posted_at: str) -> list[ScoutedListing]:
    found: list[ScoutedListing] = []
    for row in rows:
        if len(found) >= MAX_LISTINGS_PER_CATEGORY:
            break
        resolved = resolve_category(category, str(row.get("title") or ""))
        if resolved is None:
            continue
        neighborhood = accept_place(str(row.get("location") or ""), require_bay=True)
        if neighborhood is None:
            continue
        listing = build_listing(
            source=NAME,
            external_id=str(row["external_id"]),
            category=resolved,
            title=str(row["title"]),
            price=int(row["price"]),
            neighborhood=neighborhood,
            source_url=str(row["url"]),
            photos=list(row.get("photos") or []),
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
        keyword = QUERIES.get(category)
        if keyword is None:
            continue
        try:
            body = fetcher.fetch(NAME, search_url(keyword), ALLOWED_HOSTS)
        except PageLimit:
            break
        except ScoutStopped as exc:
            return SourceBatch(found, stopped=True, reason=exc.reason, message=exc.message)
        found.extend(_to_listings(parse_search_page(body), category, posted_at))
    return SourceBatch(found)


def collect_query(query: str, category: str | None, fetcher: PageFetcher, posted_at: str):
    """One public search page. Listings outside the Bay Area are dropped."""

    from backend.app.sources.aggregate import SourceBatch

    try:
        body = fetcher.fetch(NAME, search_url(query), ALLOWED_HOSTS)
    except PageLimit:
        return SourceBatch()
    except ScoutStopped as exc:
        return SourceBatch([], stopped=True, reason=exc.reason, message=exc.message)
    return SourceBatch(_to_listings(parse_search_page(body), category, posted_at))
