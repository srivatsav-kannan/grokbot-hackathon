"""Buyer and Seller agents. Person B (@srivatsav-kannan) owns this file.

negotiate() may use the two bounds to decide. It must not log them, return them
as fields, or mention them by name in message text. Visible offers stay inside
the overlap when the agents can agree.

Keep the signature. Replace stub_negotiate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from backend.app.agents.llm import complete
from backend.app.repository import ListingRecord
from backend.app.schemas import NegotiationMessage, Outcome


@dataclass(frozen=True)
class NegotiationDraft:
    outcome: Outcome
    messages: list[NegotiationMessage]


def _at(offset_s: int) -> str:
    moment = datetime.now(timezone.utc) + timedelta(seconds=offset_s)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def stub_negotiate(listing: ListingRecord, buyer_max: int, seller_min: int) -> NegotiationDraft:
    if buyer_max < seller_min:
        return NegotiationDraft(
            outcome="no_deal",
            messages=[
                NegotiationMessage(
                    from_="buyer",
                    kind="offer",
                    amount=None,
                    text="I want this, but I can't meet the asking price.",
                    at=_at(0),
                ),
                NegotiationMessage(
                    from_="seller",
                    kind="decline",
                    amount=None,
                    text="I have to pass at that range.",
                    at=_at(2),
                ),
            ],
        )
    if seller_min <= listing.price <= buyer_max:
        amount = listing.price
    else:
        amount = (buyer_max + seller_min) // 2
    return NegotiationDraft(
        outcome="deal",
        messages=[
            NegotiationMessage(
                from_="buyer",
                kind="offer",
                amount=amount,
                text=f"I can do {amount} if I pick it up this week.",
                at=_at(0),
            ),
            NegotiationMessage(
                from_="seller",
                kind="accept",
                amount=amount,
                text="That works. Pickup this week.",
                at=_at(2),
            ),
        ],
    )


def negotiate(listing: ListingRecord, buyer_max: int, seller_min: int) -> NegotiationDraft:
    # The prompt must not include the hidden bounds.
    complete(f"Negotiate listing {listing.id} with asking price {listing.price}.")
    return stub_negotiate(listing, buyer_max, seller_min)
