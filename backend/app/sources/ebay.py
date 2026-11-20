"""eBay public local-pickup search near San Francisco.

With EBAY_APP_ID set, Scout calls the public Finding API once per category.
Without it, Scout reads the public search page. A block stops this source
for the run. Scout does not switch methods after a block, and it does not
sign in.
"""

from __future__ import annotations

import json
import os
import re
from urllib.parse import urlencode

from backend.app.sources.errors import PageLimit, ScoutStopped
from backend.app.sources.fetch import PageFetcher
from backend.app.sources.listing import (
    MAX_LISTINGS_PER_CATEGORY,
    ScoutedListing,
    build_listing,
    parse_price,
    resolve_category,
    scrub,
)
from backend.app.sources.places import location_is_outside

NAME = "ebay"
ALLOWED_HOSTS = ("ebay.com",)
QUERIES: dict[str, str] = {
    "bikes": "bicycle",
    "computers": "laptop",
    "furniture": "sofa",
}
DESCRIPTION = "Found on a public eBay local-pickup search near San Francisco. Open the source link for the full post."
POSTAL_CODE = "94102"

_LI_RE = re.compile(r'<li[^>]*class="[^"]*\bs-item\b[^"]*"[^>]*>(.*?)</li>', re.S)
_HREF_RE = re.compile(r'href="(https://www\.ebay\.com/itm/[^"]+)"')
_TITLE_RE = re.compile(r'class="s-item__title"[^>]*>(.*?)</(?:div|span|h3)>', re.S)
_PRICE_RE = re.compile(r'class="s-item__price"[^>]*>(.*?)</span>', re.S)
_LOC_RE = re.compile(
    r'class="[^"]*(?:s-item__location|s-item__itemLocation)[^"]*"[^>]*>(.*?)</span>',
    re.S,
)
_IMG_RE = re.compile(r'<img[^>]+src="(https://i\.ebayimg\.com/[^"]+)"')
_ITEM_ID_RE = re.compile(r"/itm/(?:[^/?#]+/)?(\d{9,})")


def search_page_url(keyword: str) -> str:
    params = {
        "_nkw": keyword,
        "LH_LPickup": "1",
        "_stpos": POSTAL_CODE,
        "_sadis": "50",
        "_ipg": "25",
        "rt": "nc",
        "_fcid": "1",
    }
    return "https://www.ebay.com/sch/i.html?" + urlencode(params)


def finding_url(app_id: str, keyword: str) -> str:
    params = {
        "OPERATION-NAME": "findItemsAdvanced",
        "SERVICE-VERSION": "1.0.0",
        "SECURITY-APPNAME": app_id,
        "RESPONSE-DATA-FORMAT": "JSON",
        "REST-PAYLOAD": "true",
        "keywords": keyword,
        "buyerPostalCode": POSTAL_CODE,
        "paginationInput.entriesPerPage": "10",
        "itemFilter(0).name": "LocalPickupOnly",
        "itemFilter(0).value": "true",
        "itemFilter(1).name": "MaxDistance",
        "itemFilter(1).value": "50",
    }
    return "https://svcs.ebay.com/services/search/FindingService/v1?" + urlencode(params)


def _text(fragment: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", fragment).split())


def _canonical_url(url: str, item_id: str) -> str:
    return f"https://www.ebay.com/itm/{item_id}" if item_id else url.split("?", 1)[0]


def parse_search_html(body: str) -> list[dict[str, object]]:
    """Public search-result markup. The placeholder 'Shop on eBay' row is skipped."""

    items: list[dict[str, object]] = []
    for block in _LI_RE.findall(body):
        href = _HREF_RE.search(block)
        title_match = _TITLE_RE.search(block)
        price_match = _PRICE_RE.search(block)
        if not href or not title_match or not price_match:
            continue
        title = scrub(_text(title_match.group(1)))
        if not title or title.lower() == "shop on ebay":
            continue
        item_id_match = _ITEM_ID_RE.search(href.group(1))
        if not item_id_match:
            continue
        price = parse_price(_text(price_match.group(1)))
        if price is None:
            continue
        location_match = _LOC_RE.search(block)
        location = scrub(_text(location_match.group(1))) if location_match else ""
        image = _IMG_RE.search(block)
        items.append(
            {
                "external_id": item_id_match.group(1),
                "title": title,
                "price": price,
                "location": location,
                "url": _canonical_url(html_unescape(href.group(1)), item_id_match.group(1)),
                "photos": [image.group(1)] if image else [],
                "posted_at": None,
            }
        )
    return items


def html_unescape(value: str) -> str:
    return value.replace("&amp;", "&")


def _first(value: object) -> object:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def parse_finding_json(body: str) -> list[dict[str, object]]:
    """eBay Finding API JSON. A Failure ack stops the source without echoing the payload."""

    try:
        data = json.loads(body)
    except ValueError as exc:
        raise ScoutStopped(
            "other",
            "eBay search returned an unexpected response. Scout stopped that source.",
        ) from exc
    root = _first(data.get("findItemsAdvancedResponse") if isinstance(data, dict) else None)
    if not isinstance(root, dict):
        raise ScoutStopped(
            "other",
            "eBay search returned an unexpected response. Scout stopped that source.",
        )
    ack = _first(root.get("ack"))
    if isinstance(ack, str) and ack.lower() == "failure":
        raise ScoutStopped(
            "other",
            "eBay search did not return results. Scout stopped that source and will not retry.",
        )
    result = _first(root.get("searchResult"))
    raw_items = result.get("item") if isinstance(result, dict) else None
    if raw_items is None:
        return []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    items: list[dict[str, object]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        item_id = _first(raw.get("itemId"))
        title = _first(raw.get("title"))
        url = _first(raw.get("viewItemURL"))
        if not isinstance(item_id, str) or not isinstance(title, str) or not isinstance(url, str):
            continue
        status = _first(raw.get("sellingStatus"))
        price_node = status.get("currentPrice") if isinstance(status, dict) else None
        price_node = _first(price_node)
        if isinstance(price_node, dict):
            price = parse_price(price_node.get("__value__"))
        else:
            price = parse_price(price_node)
        if price is None:
            continue
        location = _first(raw.get("location"))
        photo = _first(raw.get("galleryURL"))
        info = _first(raw.get("listingInfo"))
        posted = info.get("startTime") if isinstance(info, dict) else None
        posted = _first(posted)
        items.append(
            {
                "external_id": item_id,
                "title": scrub(title),
                "price": price,
                "location": location if isinstance(location, str) else "",
                "url": _canonical_url(url, item_id),
                "photos": [photo] if isinstance(photo, str) and photo.startswith("https://") else [],
                "posted_at": posted if isinstance(posted, str) else None,
            }
        )
    return items


def _to_listings(rows: list[dict[str, object]], category: str | None, posted_at: str) -> list[ScoutedListing]:
    found: list[ScoutedListing] = []
    for row in rows[:MAX_LISTINGS_PER_CATEGORY]:
        resolved = resolve_category(category, str(row.get("title") or ""))
        if resolved is None:
            continue
        location = str(row.get("location") or "")
        if location and location_is_outside(location):
            continue
        neighborhood = location.strip() or "SF Bay Area"
        if neighborhood.islower():
            neighborhood = neighborhood.title()
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

    app_id = os.environ.get("EBAY_APP_ID", "").strip()
    found: list[ScoutedListing] = []
    for category in categories:
        keyword = QUERIES.get(category)
        if keyword is None:
            continue
        url = finding_url(app_id, keyword) if app_id else search_page_url(keyword)
        try:
            body = fetcher.fetch(NAME, url, ALLOWED_HOSTS)
        except PageLimit:
            break
        except ScoutStopped as exc:
            return SourceBatch(found, stopped=True, reason=exc.reason, message=exc.message)
        try:
            rows = parse_finding_json(body) if app_id else parse_search_html(body)
        except ScoutStopped as exc:
            return SourceBatch(found, stopped=True, reason=exc.reason, message=exc.message)
        found.extend(_to_listings(rows, category, posted_at))
    return SourceBatch(found)


def collect_query(query: str, category: str | None, fetcher: PageFetcher, posted_at: str):
    """One local-pickup search for the free-text query. A block does not switch transports."""

    from backend.app.sources.aggregate import SourceBatch

    app_id = os.environ.get("EBAY_APP_ID", "").strip()
    url = finding_url(app_id, query) if app_id else search_page_url(query)
    try:
        body = fetcher.fetch(NAME, url, ALLOWED_HOSTS)
    except PageLimit:
        return SourceBatch()
    except ScoutStopped as exc:
        return SourceBatch([], stopped=True, reason=exc.reason, message=exc.message)
    try:
        rows = parse_finding_json(body) if app_id else parse_search_html(body)
    except ScoutStopped as exc:
        return SourceBatch([], stopped=True, reason=exc.reason, message=exc.message)
    return SourceBatch(_to_listings(rows, category, posted_at))
