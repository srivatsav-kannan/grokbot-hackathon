"""Appraiser. Person B (@srivatsav-kannan) owns this file.

Replace stub_appraise. Keep appraise() so callers do not change.
Verdict rule: asking price under low -> good_deal; inside [low, high] -> fair; over high -> overpriced.
"""

from __future__ import annotations

from backend.app.agents.llm import complete, parse_json_reply
from backend.app.repository import ListingRecord
from backend.app.schemas import Appraisal, Comp

# Category anchors in integer USD. Independent of the asking price so verdicts can differ.
ANCHORS: dict[str, int] = {
    "bikes": 360,
    "computers": 750,
    "furniture": 220,
}

_MAX_DOLLARS = 500_000


def verdict_for(price: int, low: int, high: int) -> str:
    if price < low:
        return "good_deal"
    if price > high:
        return "overpriced"
    return "fair"


def stub_appraise(listing: ListingRecord) -> Appraisal:
    anchor = ANCHORS.get(listing.category, listing.price)
    low = int(round(anchor * 0.8))
    high = int(round(anchor * 1.2))
    label = listing.category[:-1] if listing.category.endswith("s") else listing.category
    return Appraisal(
        estimated_value=anchor,
        low=low,
        high=high,
        comps=[
            Comp(title=f"Similar {label} nearby", price=low),
            Comp(title=f"Recent {label} sale", price=high),
        ],
        verdict=verdict_for(listing.price, low, high),  # type: ignore[arg-type]
    )


def appraise(listing: ListingRecord) -> Appraisal:
    parsed = parse_json_reply(complete(_appraisal_prompt(listing)))
    if isinstance(parsed, dict):
        appraisal = _appraisal_from_payload(listing, parsed)
        if appraisal is not None:
            return appraisal
    return stub_appraise(listing)


def _appraisal_prompt(listing: ListingRecord) -> str:
    return (
        "You price used bikes, computers, and furniture in the SF Bay Area. "
        "Reply with one JSON object only, no markdown, using integer US dollars: "
        '{"estimated_value": 340, "low": 280, "high": 420, '
        '"comps": [{"title": "Similar item nearby", "price": 300, "url": null}]}. '
        "Only give a comp url if you are sure the page exists, otherwise null. "
        "low and high are the comparable range. estimated_value must sit inside that range. "
        "Do not decide whether the asking price is a good deal. "
        "Do not include a budget, a buyer maximum, or a seller minimum.\n"
        f"Category: {listing.category}\n"
        f"Title: {listing.title}\n"
        f"Description: {listing.description}\n"
        f"Neighborhood: {listing.neighborhood}\n"
        f"Asking price: {listing.price}"
    )


def _appraisal_from_payload(listing: ListingRecord, payload: dict) -> Appraisal | None:
    low = _dollars(payload.get("low"))
    high = _dollars(payload.get("high"))
    estimated = _dollars(payload.get("estimated_value"))
    if low is None or high is None or estimated is None or low > high:
        return None
    if estimated < low or estimated > high:
        estimated = min(max(estimated, low), high)
    return Appraisal(
        estimated_value=estimated,
        low=low,
        high=high,
        comps=_comps(payload.get("comps"), low, high),
        verdict=verdict_for(listing.price, low, high),  # type: ignore[arg-type]
    )


def _comps(raw: object, low: int, high: int) -> list[Comp]:
    comps: list[Comp] = []
    if isinstance(raw, list):
        for item in raw[:6]:
            if not isinstance(item, dict):
                continue
            title = item.get("title")
            price = _dollars(item.get("price"))
            url = item.get("url")
            if not isinstance(title, str) or not title.strip() or price is None:
                continue
            if not isinstance(url, str) or not url.strip():
                url = None
            elif "example.com" in url:
                url = None
            comps.append(Comp(title=title.strip()[:120], price=price, url=url.strip()[:300] if url else None))
    if comps:
        return comps
    return [
        Comp(title="Lower comparable", price=low),
        Comp(title="Higher comparable", price=high),
    ]


def _dollars(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        number = value
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    elif isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("$", "")
        if not cleaned.isdigit():
            return None
        number = int(cleaned)
    else:
        return None
    if number < 1 or number > _MAX_DOLLARS:
        return None
    return number
