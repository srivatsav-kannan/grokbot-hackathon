"""Normalized listing Scout stores. Field names match ListingRecord, plus source."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from backend.app.repository import ListingRecord
from backend.app.sources.places import location_is_bay, location_is_outside

MAX_LISTINGS_PER_CATEGORY = 8

PLACEHOLDERS: dict[str, str] = {
    "bikes": "/placeholders/bike.svg",
    "computers": "/placeholders/computer.svg",
    "furniture": "/placeholders/furniture.svg",
}

DISPLAY_NAMES: dict[str, str] = {
    "craigslist": "Craigslist",
    "ebay": "eBay",
    "offerup": "OfferUp",
    "mercari": "Mercari",
    "facebook": "Facebook Marketplace",
    "nextdoor": "Nextdoor",
}

_ID_PREFIX: dict[str, str] = {
    "craigslist": "cl",
    "ebay": "eb",
    "offerup": "ou",
    "mercari": "mc",
    "facebook": "fb",
    "nextdoor": "nd",
}

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")

# First match wins. Used when a free-text search did not name a category.
_CATEGORY_TERMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("bikes", ("bike", "bicycle", "cycling", "ebike", "e-bike")),
    ("computers", ("laptop", "computer", "desktop", "monitor", "macbook", "imac", "chromebook")),
    ("furniture", ("sofa", "couch", "desk", "table", "chair", "dresser", "furniture", "bookshelf", "sectional")),
)


def category_from_text(*parts: str) -> str | None:
    """Map free text to bikes, computers, or furniture. None when it does not say."""

    blob = " ".join(parts).lower()
    for category, terms in _CATEGORY_TERMS:
        if any(re.search(rf"\b{re.escape(term)}\b", blob) for term in terms):
            return category
    return None


def resolve_category(category: str | None, title: str) -> str | None:
    """Use the requested category, or classify the title when the search was open."""

    if category in PLACEHOLDERS:
        return category
    return category_from_text(title)


def scrub(text: str) -> str:
    """Drop emails and phone numbers. Scout does not store contact details."""

    text = _EMAIL_RE.sub("", text)
    text = _PHONE_RE.sub("", text)
    return " ".join(text.split()).strip(" -,")


def parse_price(raw: object) -> int | None:
    """Integer USD. Missing, zero, and non-numeric prices are skipped."""

    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, (int, float)):
        value = int(raw)
        return value if value > 0 else None
    digits = re.sub(r"[^\d.]", "", str(raw))
    if not digits:
        return None
    try:
        value = int(float(digits))
    except ValueError:
        return None
    return value if value > 0 else None


def tidy_place(text: str) -> str:
    text = scrub(text)
    if not text:
        return "SF Bay Area"
    if text.islower():
        return text.title()
    return text


def accept_place(text: str, *, require_bay: bool) -> str | None:
    """Neighborhood to store, or None when the listing is outside the Bay."""

    cleaned = scrub(text)
    if require_bay:
        if not location_is_bay(cleaned):
            return None
        return tidy_place(cleaned)
    if cleaned and location_is_outside(cleaned):
        return None
    return tidy_place(cleaned)


@dataclass(frozen=True)
class ScoutedListing(ListingRecord):
    """A ListingRecord plus the marketplace name and that marketplace's own id.

    `source` defaults to craigslist and `external_id` to empty so older callers
    that only read ListingRecord fields keep working. `source_url` is the
    original public listing URL.
    """

    source: str = "craigslist"
    external_id: str = ""


def listing_id(source: str, external_id: str, source_url: str) -> str:
    """Stable id. Craigslist keeps the historical hash of the public URL."""

    prefix = _ID_PREFIX.get(source, source[:2] or "sc")
    if source == "craigslist":
        digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:12]
    else:
        digest = hashlib.sha256(f"{source}:{external_id}".encode("utf-8")).hexdigest()[:12]
    return f"lst_{prefix}_{digest}"


def build_listing(
    *,
    source: str,
    external_id: str,
    category: str,
    title: str,
    price: int,
    neighborhood: str,
    source_url: str,
    photos: list[str],
    posted_at: str,
    description: str | None = None,
) -> ScoutedListing | None:
    """Return a normalized listing, or None when a required public field is missing."""

    title = scrub(title)[:120]
    if not title or price <= 0 or not external_id or not source_url.startswith("https://"):
        return None
    if category not in PLACEHOLDERS:
        return None
    kept = [url for url in photos if isinstance(url, str) and url.startswith("https://")][:4]
    if not kept:
        kept = [PLACEHOLDERS[category]]
    if description is None:
        label = DISPLAY_NAMES.get(source, source)
        description = f"Found on a public {label} page. Open the source link for the full post."
    return ScoutedListing(
        id=listing_id(source, external_id, source_url),
        category=category,
        title=title,
        description=description,
        price=price,
        photos=kept,
        neighborhood=neighborhood or "SF Bay Area",
        source_url=source_url,
        posted_at=posted_at,
        origin="scout",
        source=source,
        external_id=external_id,
    )


def dedupe(listings: list[ScoutedListing]) -> list[ScoutedListing]:
    """Drop later copies of the same marketplace item. Different sources both stay."""

    seen: set[tuple[str, str]] = set()
    kept: list[ScoutedListing] = []
    for item in listings:
        key = (item.source, item.external_id)
        if not item.external_id or key in seen:
            continue
        seen.add(key)
        kept.append(item)
    return kept
