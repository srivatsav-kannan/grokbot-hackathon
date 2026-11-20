"""Mercari public search pages.

Scout reads the search HTML only. Items are kept when they name an SF Bay
Area location. A 401/403/429 or a CAPTCHA stops this source for the run.
Scout does not sign in or try to get past a challenge.
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

NAME = "mercari"
ALLOWED_HOSTS = ("mercari.com",)
QUERIES: dict[str, str] = {
    "bikes": "bicycle",
    "computers": "laptop",
    "furniture": "sofa",
}
DESCRIPTION = "Found on a public Mercari search page. Open the source link for the full post."
_NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def search_url(keyword: str) -> str:
    return "https://www.mercari.com/search/?" + urlencode({"keyword": keyword})


def _is_item(node: dict) -> bool:
    title = node.get("name") if isinstance(node.get("name"), str) else node.get("title")
    if not isinstance(title, str) or len(title.strip()) < 2:
        return False
    if not isinstance(node.get("id"), str) or not node["id"].strip():
        return False
    if not isinstance(node.get("price"), (int, float, str)) or isinstance(node.get("price"), bool):
        return False
    return any(key in node for key in ("thumbnails", "photos", "images", "image"))


def _walk_items(node: object):
    if isinstance(node, dict):
        if _is_item(node):
            yield node
            return
        for value in node.values():
            yield from _walk_items(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_items(value)


def _location(node: dict) -> str:
    for key in ("itemLocation", "city", "location"):
        value = node.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            city = value.get("city") or value.get("name")
            if isinstance(city, str):
                return city
    return ""


def _photos(node: dict) -> list[str]:
    raw = node.get("thumbnails") or node.get("photos") or node.get("images") or node.get("image")
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    return [url for url in raw if isinstance(url, str) and url.startswith("https://")]


def parse_search_page(body: str) -> list[dict[str, object]]:
    match = _NEXT_RE.search(body)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return []
    items: list[dict[str, object]] = []
    for node in _walk_items(data):
        title = node.get("name") if isinstance(node.get("name"), str) else node.get("title")
        price = parse_price(node.get("price"))
        if price is None or not isinstance(title, str):
            continue
        external_id = str(node["id"])
        url = node.get("itemUrl") or node.get("url")
        if not isinstance(url, str) or not url.startswith("https://www.mercari.com/"):
            url = f"https://www.mercari.com/us/item/{external_id}/"
        posted = node.get("updated") or node.get("created") or node.get("postedAt")
        items.append(
            {
                "external_id": external_id,
                "title": title,
                "price": price,
                "location": _location(node),
                "url": url,
                "photos": _photos(node),
                "posted_at": posted if isinstance(posted, str) else None,
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
        when = row.get("posted_at")
        listing = build_listing(
            source=NAME,
            external_id=str(row["external_id"]),
            category=resolved,
            title=str(row["title"]),
            price=int(row["price"]),
            neighborhood=neighborhood,
            source_url=str(row["url"]),
            photos=list(row.get("photos") or []),
            posted_at=when if isinstance(when, str) and "T" in when else posted_at,
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
    """One public search page. A challenge stops this source and is not retried."""

    from backend.app.sources.aggregate import SourceBatch

    try:
        body = fetcher.fetch(NAME, search_url(query), ALLOWED_HOSTS)
    except PageLimit:
        return SourceBatch()
    except ScoutStopped as exc:
        return SourceBatch([], stopped=True, reason=exc.reason, message=exc.message)
    return SourceBatch(_to_listings(parse_search_page(body), category, posted_at))
