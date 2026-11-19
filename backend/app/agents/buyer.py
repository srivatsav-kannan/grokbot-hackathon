"""Buyer agent. Person B (@srivatsav-kannan) owns this file.

parse_want(text) -> WantCriteria          public criteria only
match_listings(criteria) -> list[Match]   ranked seller listings
choose_hunt_targets(criteria) -> list[Match]

private_max_from_text() is server-only. Its return value is stored by the
service layer and must never be placed on WantCriteria, a response model, or a log line.

Replace the stub bodies. Keep the signatures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.app import repository as repo
from backend.app.agents.llm import complete
from backend.app.repository import ListingRecord

MAX_HUNT_MATCHES = 3

_CATEGORY_WORDS: tuple[tuple[str, str], ...] = (
    ("bike", "bikes"),
    ("bicycle", "bikes"),
    ("laptop", "computers"),
    ("computer", "computers"),
    ("desktop", "computers"),
    ("monitor", "computers"),
    ("furniture", "furniture"),
    ("desk", "furniture"),
    ("sofa", "furniture"),
    ("table", "furniture"),
    ("shelf", "furniture"),
    ("bookshelf", "furniture"),
)

_AREA_WORDS: tuple[tuple[str, str], ...] = (
    ("san francisco", "San Francisco"),
    ("sf", "San Francisco"),
    ("oakland", "Oakland"),
    ("berkeley", "Berkeley"),
    ("palo alto", "Palo Alto"),
    ("sunnyvale", "Sunnyvale"),
)

_STOP = {
    "a",
    "an",
    "the",
    "in",
    "on",
    "for",
    "with",
    "and",
    "or",
    "to",
    "of",
    "under",
    "below",
    "over",
    "above",
    "less",
    "than",
    "max",
    "budget",
    "want",
    "looking",
    "need",
    "my",
}


@dataclass(frozen=True)
class WantCriteria:
    category: str | None
    area: str | None
    keywords: list[str]


@dataclass(frozen=True)
class Match:
    listing_id: str
    score: float
    reason: str


_MONEY = re.compile(
    r"(?i)(?:\b(?:under|below|over|above|max|budget|less\s+than)\s*)?\$\s*\d+"
    r"|\b(?:under|below|over|above|less\s+than)\s+\$?\d+\b"
)
_MAX_IN_TEXT = re.compile(
    r"(?i)\b(?:under|below|max|budget|less\s+than)\s*\$?\s*(\d+)\b|\$\s*(\d+)"
)


def redact_money(text: str) -> str:
    cleaned = _MONEY.sub(" ", text)
    return " ".join(cleaned.split())


def private_max_from_text(text: str) -> int | None:
    """Pull a ceiling out of free text. Caller stores it. Never return it over HTTP."""

    match = _MAX_IN_TEXT.search(text)
    if match is None:
        return None
    raw = match.group(1) or match.group(2)
    return int(raw)


def stub_parse_want(text: str) -> WantCriteria:
    lowered = text.lower()
    category: str | None = None
    for needle, value in _CATEGORY_WORDS:
        if re.search(rf"\b{re.escape(needle)}\b", lowered):
            category = value
            break
    area: str | None = None
    for needle, value in _AREA_WORDS:
        if re.search(rf"\b{re.escape(needle)}\b", lowered):
            area = value
            break
    keywords: list[str] = []
    seen: set[str] = set()
    redacted = redact_money(lowered)
    for token in re.findall(r"[a-z0-9]+", redacted):
        if token.isdigit() or token in _STOP or token in seen:
            continue
        if any(token == needle or token == needle + "s" for needle, _value in _CATEGORY_WORDS):
            continue
        if any(token == part for needle, _value in _AREA_WORDS for part in needle.split()):
            continue
        seen.add(token)
        keywords.append(token)
    return WantCriteria(category=category, area=area, keywords=keywords[:8])


def parse_want(text: str) -> WantCriteria:
    complete("Parse a classifieds want into category, area, and keywords. Omit any budget.")
    return stub_parse_want(text)


def _score(listing: ListingRecord, criteria: WantCriteria) -> int:
    score = 0
    if criteria.category and listing.category == criteria.category:
        score += 3
    if criteria.area and criteria.area.lower() in listing.neighborhood.lower():
        score += 2
    haystack = f"{listing.title} {listing.description}".lower()
    for keyword in criteria.keywords:
        if keyword in haystack:
            score += 1
    return score


def _reason(listing: ListingRecord, criteria: WantCriteria) -> str:
    if criteria.keywords and criteria.area and criteria.area.lower() in listing.neighborhood.lower():
        return f"{criteria.keywords[0].capitalize()} in {criteria.area}."
    if criteria.keywords:
        return f"Matches {criteria.keywords[0]}."
    return "Matches the request."


def stub_match_listings(criteria: WantCriteria) -> list[Match]:
    scored: list[Match] = []
    for listing in repo.list_listings(None, None):
        raw = _score(listing, criteria)
        if raw <= 0:
            continue
        scored.append(
            Match(
                listing_id=listing.id,
                score=min(1.0, raw / 6),
                reason=_reason(listing, criteria),
            )
        )
    scored.sort(key=lambda item: (-item.score, item.listing_id))
    return scored


def match_listings(criteria: WantCriteria) -> list[Match]:
    complete(
        "Rank seller listings for a want. "
        f"category={criteria.category} area={criteria.area} keywords={', '.join(criteria.keywords)}"
    )
    return stub_match_listings(criteria)


def choose_hunt_targets(criteria: WantCriteria) -> list[Match]:
    """Full ranking. The service drops over-ceiling rows, then keeps MAX_HUNT_MATCHES.

    Do not read or return a private ceiling from this function.
    """

    return match_listings(criteria)
