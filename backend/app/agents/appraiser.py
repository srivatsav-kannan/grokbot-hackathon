"""Appraiser. Person B (@srivatsav-kannan) owns this file.

Replace stub_appraise. Keep appraise() so callers do not change.
Verdict rule: asking price under low -> good_deal; inside [low, high] -> fair; over high -> overpriced.
"""

from __future__ import annotations

from backend.app.agents.llm import complete
from backend.app.repository import ListingRecord
from backend.app.schemas import Appraisal, Comp

# Category anchors in integer USD. Independent of the asking price so verdicts can differ.
ANCHORS: dict[str, int] = {
    "bikes": 360,
    "computers": 750,
    "furniture": 220,
}


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
            Comp(title=f"Similar {label} nearby", price=low, url="https://example.com/comps/low"),
            Comp(title=f"Recent {label} sale", price=high, url="https://example.com/comps/high"),
        ],
        verdict=verdict_for(listing.price, low, high),  # type: ignore[arg-type]
    )


def appraise(listing: ListingRecord) -> Appraisal:
    complete(f"Appraise a {listing.category} listing titled {listing.title} asking {listing.price}.")
    return stub_appraise(listing)
