"""Inspector. Person B (@srivatsav-kannan) owns this file.

Replace stub_inspect. Keep inspect(). Reasons are one plain sentence each.
"""

from __future__ import annotations

from backend.app.agents.llm import complete
from backend.app.repository import ListingRecord
from backend.app.schemas import Appraisal, Inspection, Signal


def stub_inspect(listing: ListingRecord, appraisal: Appraisal) -> Inspection:
    signals: list[Signal] = []
    if listing.price < int(appraisal.low * 0.5):
        signals.append(
            Signal(
                code="price_far_below_comps",
                reason="The asking price is far below similar listings.",
            )
        )
    elif listing.price < appraisal.low:
        signals.append(
            Signal(
                code="price_below_comps",
                reason="The asking price is below the usual range for similar listings.",
            )
        )
    if len(listing.description.strip()) < 40:
        signals.append(
            Signal(
                code="thin_description",
                reason="The description is too short to judge the item's condition.",
            )
        )
    if any(signal.code == "price_far_below_comps" for signal in signals):
        trust_level = "low"
    elif signals:
        trust_level = "medium"
    else:
        trust_level = "high"
    return Inspection(trust_level=trust_level, signals=signals)  # type: ignore[arg-type]


def inspect(listing: ListingRecord, appraisal: Appraisal) -> Inspection:
    complete(f"Inspect listing {listing.id} in {listing.neighborhood} for scam signals.")
    return stub_inspect(listing, appraisal)
