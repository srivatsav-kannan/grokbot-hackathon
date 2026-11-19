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
from backend.app.agents.llm import complete, parse_json_reply
from backend.app.repository import ListingRecord

MAX_HUNT_MATCHES = 3

_CATEGORY_WORDS: tuple[tuple[str, str], ...] = (
    ("e-bike", "bikes"),
    ("ebike", "bikes"),
    ("bicycle", "bikes"),
    ("bike", "bikes"),
    ("macbook", "computers"),
    ("laptop", "computers"),
    ("desktop", "computers"),
    ("monitor", "computers"),
    ("computer", "computers"),
    ("bookshelf", "furniture"),
    ("bookcase", "furniture"),
    ("dresser", "furniture"),
    ("couch", "furniture"),
    ("sofa", "furniture"),
    ("chair", "furniture"),
    ("desk", "furniture"),
    ("table", "furniture"),
    ("shelf", "furniture"),
    ("furniture", "furniture"),
)

_AREA_WORDS: tuple[tuple[str, str], ...] = (
    ("san francisco", "San Francisco"),
    ("palo alto", "Palo Alto"),
    ("daly city", "Daly City"),
    ("san jose", "San Jose"),
    ("hayes valley", "Hayes Valley"),
    ("richmond district", "Richmond District"),
    ("bernal heights", "Bernal Heights"),
    ("oakland", "Oakland"),
    ("berkeley", "Berkeley"),
    ("sunnyvale", "Sunnyvale"),
    ("temescal", "Temescal"),
    ("mission", "Mission"),
    ("soma", "SoMa"),
    ("sf", "San Francisco"),
)

_GENERIC_CATEGORY = {
    "bike",
    "bikes",
    "bicycle",
    "bicycles",
    "ebike",
    "computer",
    "computers",
    "furniture",
}

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
    "up",
    "under",
    "below",
    "over",
    "above",
    "less",
    "than",
    "more",
    "most",
    "no",
    "at",
    "max",
    "maximum",
    "budget",
    "price",
    "dollars",
    "dollar",
    "usd",
    "want",
    "looking",
    "need",
    "my",
    "around",
    "about",
}

_AMOUNT_TOKEN = r"(\d{1,3}(?:,\d{3})+|\d+)"
_CEILING = re.compile(
    rf"(?i)\b(?:under|below|less\s+than|no\s+more\s+than|up\s+to|at\s+most|"
    rf"max(?:imum)?(?:\s+of)?|budget(?:\s+of)?)\s*\$?\s*{_AMOUNT_TOKEN}(?:\.0+)?\b"
    rf"|\$?\s*{_AMOUNT_TOKEN}(?:\.0+)?\s*(?:max|budget|or\s+less|or\s+under)\b"
)
_DOLLARS = re.compile(rf"(?i)\$\s*{_AMOUNT_TOKEN}(?:\.0+)?")
_OVER_ONLY = re.compile(
    rf"(?i)\b(?:over|above|more\s+than|at\s+least)\s+\$?\s*{_AMOUNT_TOKEN}(?:\.0+)?\b"
)
_MONEY = re.compile(
    r"(?i)(?:\b(?:under|below|over|above|less\s+than|no\s+more\s+than|up\s+to|at\s+most|"
    r"more\s+than|at\s+least|max(?:imum)?(?:\s+of)?|budget(?:\s+of)?)\s*)?\$\s*\d[\d,]*(?:\.\d+)?"
    r"|\b(?:under|below|over|above|less\s+than|no\s+more\s+than|up\s+to|at\s+most|"
    r"more\s+than|at\s+least|max(?:imum)?(?:\s+of)?|budget(?:\s+of)?)\s+\$?\d[\d,]*(?:\.\d+)?\b"
    r"|\$?\d[\d,]*(?:\.\d+)?\s*(?:max|budget|or\s+less|or\s+under)\b"
)


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


def redact_money(text: str) -> str:
    cleaned = _MONEY.sub(" ", text)
    return " ".join(cleaned.split())


def private_max_from_text(text: str) -> int | None:
    """Pull a ceiling out of free text. Caller stores it. Never return it over HTTP."""

    match = _CEILING.search(text)
    if match is not None:
        raw = next(group for group in match.groups() if group)
        return _parse_amount(raw)
    for found in _DOLLARS.finditer(text):
        window = text[max(0, found.start() - 24) : found.end()]
        if _OVER_ONLY.search(window):
            continue
        return _parse_amount(found.group(1))
    return None


def stub_parse_want(text: str) -> WantCriteria:
    lowered = text.lower()
    category = _category_in(lowered)
    area = _area_in(lowered)
    keywords: list[str] = []
    seen: set[str] = set()
    redacted = redact_money(lowered)
    for token in re.findall(r"[a-z0-9]+", redacted):
        if not _keep_keyword(token, seen):
            continue
        seen.add(token)
        keywords.append(token)
    return WantCriteria(category=category, area=area, keywords=keywords[:8])


def parse_want(text: str) -> WantCriteria:
    redacted = redact_money(text)
    parsed = parse_json_reply(complete(_parse_prompt(redacted)))
    if isinstance(parsed, dict):
        criteria = _criteria_from_model(parsed)
        if criteria is not None:
            return criteria
    return stub_parse_want(text)


def _score(listing: ListingRecord, criteria: WantCriteria) -> float:
    if criteria.category and listing.category != criteria.category:
        return 0.0
    score = 0.0
    if criteria.category and listing.category == criteria.category:
        score += 4
    if criteria.area and criteria.area.lower() in listing.neighborhood.lower():
        score += 3
    title = listing.title.lower()
    description = listing.description.lower()
    hits = 0
    for keyword in criteria.keywords:
        if _contains_word(title, keyword):
            score += 2.5
            hits += 1
        elif _contains_word(description, keyword):
            score += 1.0
            hits += 1
    if len(criteria.keywords) >= 2:
        phrase = " ".join(criteria.keywords)
        if phrase in title:
            score += 2
        elif phrase in description:
            score += 1
    if criteria.keywords and hits == len(criteria.keywords):
        score += 1
    appraisal = repo.get_appraisal(listing.id)
    if appraisal is not None:
        if appraisal.verdict == "good_deal":
            score += 0.5
        elif appraisal.verdict == "overpriced":
            score -= 0.25
    inspection = repo.get_inspection(listing.id)
    if inspection is not None:
        if inspection.trust_level == "low":
            score -= 0.75
        elif inspection.trust_level == "high":
            score += 0.25
    return score


def _reason(listing: ListingRecord, criteria: WantCriteria) -> str:
    subject = criteria.keywords[0].capitalize() if criteria.keywords else "This"
    if criteria.area and criteria.area.lower() in listing.neighborhood.lower():
        return f"{subject} in {criteria.area} matches this listing."
    if criteria.keywords:
        return f"The listing mentions {criteria.keywords[0]}."
    return "The category matches the request."


def stub_match_listings(criteria: WantCriteria) -> list[Match]:
    scored: list[Match] = []
    for listing in repo.list_listings(None, None):
        raw = _score(listing, criteria)
        if raw <= 0:
            continue
        scored.append(
            Match(
                listing_id=listing.id,
                score=min(1.0, round(raw / 12, 4)),
                reason=_reason(listing, criteria),
            )
        )
    scored.sort(key=lambda item: (-item.score, item.listing_id))
    return scored


def match_listings(criteria: WantCriteria) -> list[Match]:
    ranked = stub_match_listings(criteria)
    catalog = {listing.id: listing for listing in repo.list_listings(None, None)}
    parsed = parse_json_reply(complete(_match_prompt(criteria, ranked, catalog)))
    if isinstance(parsed, dict):
        noted = _apply_notes(ranked, parsed)
        if noted is not None:
            return noted
    return ranked


def choose_hunt_targets(criteria: WantCriteria) -> list[Match]:
    """Full ranking. The service drops over-ceiling rows, then keeps MAX_HUNT_MATCHES.

    Do not read or return a private ceiling from this function.
    """

    return match_listings(criteria)


def _parse_prompt(redacted: str) -> str:
    return (
        "Extract a classifieds want. Reply with one JSON object only: "
        '{"category": "bikes", "area": "San Francisco", "keywords": ["road"]}. '
        "category is bikes, computers, furniture, or null. "
        "area is a public neighborhood or city, or null. "
        "keywords are item words, at most 8. "
        "Do not include a price, a budget, a maximum, or a dollar amount.\n"
        f"Want: {redacted}"
    )


def _match_prompt(
    criteria: WantCriteria,
    ranked: list[Match],
    catalog: dict[str, ListingRecord],
) -> str:
    lines: list[str] = []
    for match in ranked[:8]:
        listing = catalog.get(match.listing_id)
        if listing is None:
            continue
        lines.append(
            f"{listing.id} | {listing.category} | {listing.title} | "
            f"{listing.neighborhood} | asking {listing.price}"
        )
    keywords = ", ".join(criteria.keywords)
    return (
        "Write one short public reason for each candidate listing. "
        "Reply with JSON only: "
        '{"notes": [{"listing_id": "lst_x", "reason": "One sentence."}]}. '
        "Do not include a buyer maximum, a seller minimum, or any private budget. "
        "Do not invent prices.\n"
        f"Category: {criteria.category}\n"
        f"Area: {criteria.area}\n"
        f"Keywords: {keywords}\n"
        + "\n".join(lines)
    )


def _criteria_from_model(payload: dict) -> WantCriteria | None:
    if not any(key in payload for key in ("category", "area", "keywords")):
        return None
    if "keywords" in payload:
        keywords = _keywords_from(payload.get("keywords"))
        if keywords is None:
            return None
    else:
        keywords = []
    return WantCriteria(
        category=_category_value(payload.get("category")),
        area=_area_value(payload.get("area")),
        keywords=keywords[:8],
    )


def _apply_notes(ranked: list[Match], payload: dict) -> list[Match] | None:
    notes = payload.get("notes")
    if not isinstance(notes, list):
        return None
    reasons: dict[str, str] = {}
    for item in notes:
        if not isinstance(item, dict):
            continue
        listing_id = item.get("listing_id")
        reason = item.get("reason")
        if not isinstance(listing_id, str) or not isinstance(reason, str):
            continue
        sentence = " ".join(reason.split())
        lowered = sentence.lower()
        if not sentence or len(sentence) > 240:
            continue
        if "buyer_max" in lowered or "seller_min" in lowered or "price_limits" in lowered:
            continue
        reasons[listing_id] = sentence
    if not reasons:
        return None
    return [
        Match(match.listing_id, match.score, reasons.get(match.listing_id, match.reason))
        for match in ranked
    ]


def _category_in(lowered: str) -> str | None:
    for needle, value in _CATEGORY_WORDS:
        if re.search(rf"\b{re.escape(needle)}\b", lowered):
            return value
    return None


def _area_in(lowered: str) -> str | None:
    for needle, value in _AREA_WORDS:
        if re.search(rf"\b{re.escape(needle)}\b", lowered):
            return value
    return None


def _category_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip().lower()
    if cleaned in {"bikes", "computers", "furniture"}:
        return cleaned
    return _category_in(cleaned)


def _area_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    if not cleaned or re.search(r"\d", cleaned) or len(cleaned) > 60:
        return None
    return _area_in(cleaned.lower()) or cleaned


def _keywords_from(value: object) -> list[str] | None:
    if value is None:
        return []
    if isinstance(value, str):
        tokens = re.findall(r"[a-z0-9]+", value.lower())
    elif isinstance(value, list):
        tokens = []
        for item in value:
            if not isinstance(item, str):
                return None
            tokens.extend(re.findall(r"[a-z0-9]+", item.lower()))
    else:
        return None
    keywords: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if not _keep_keyword(token, seen):
            continue
        seen.add(token)
        keywords.append(token)
    return keywords


def _keep_keyword(token: str, seen: set[str]) -> bool:
    if token.isdigit() or token in _STOP or token in seen or token in _GENERIC_CATEGORY:
        return False
    if any(token == part for needle, _value in _AREA_WORDS for part in needle.split()):
        return False
    return True


def _contains_word(haystack: str, keyword: str) -> bool:
    return re.search(rf"\b{re.escape(keyword)}\b", haystack) is not None


def _parse_amount(raw: str) -> int | None:
    cleaned = raw.replace(",", "")
    if not cleaned.isdigit():
        return None
    return int(cleaned)
