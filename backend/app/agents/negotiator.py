"""Buyer and Seller agents. Person B (@srivatsav-kannan) owns this file.

negotiate() may use the two bounds to decide. It must not log them, return them
as fields, or mention them by name in message text. Visible offers stay inside
the overlap when the agents can agree.

The model only phrases lines that code already priced. It never sees the bounds.
Keep the signature. Replace stub_negotiate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from backend.app.agents.llm import complete, message_effort, message_model, parse_json_reply
from backend.app.repository import ListingRecord
from backend.app.schemas import NegotiationMessage, Outcome

_Turn = tuple[str, str, int | None]


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
    turns = _turns(listing.price, buyer_max, seller_min)
    texts = _texts(listing, turns, buyer_max, seller_min)
    messages = [
        NegotiationMessage(
            from_=speaker,  # type: ignore[arg-type]
            kind=kind,  # type: ignore[arg-type]
            amount=amount,
            text=text,
            at=_at(index * 2),
        )
        for index, ((speaker, kind, amount), text) in enumerate(zip(turns, texts))
    ]
    outcome: Outcome = "deal" if turns[-1][1] == "accept" else "no_deal"
    return NegotiationDraft(outcome=outcome, messages=messages)


def _turns(ask: int, buyer_max: int, seller_min: int) -> list[_Turn]:
    if buyer_max < seller_min:
        return _no_deal_turns(ask, buyer_max, seller_min)
    return _deal_turns(ask, seller_min, buyer_max)


def _deal_turns(ask: int, low: int, high: int) -> list[_Turn]:
    if low <= ask <= high:
        preferred = ask
    else:
        preferred = (low + high) // 2
    target = _inside(low, high, preferred)
    opening = _inside(low, high, target - max(10, (target - low) // 4))
    if opening >= target:
        return [("buyer", "offer", opening), ("seller", "accept", opening)]
    if target - opening >= 40:
        middle = _inside(low, high, (opening + target) // 2)
        if opening < middle < target:
            return [
                ("buyer", "offer", opening),
                ("seller", "counter", middle),
                ("buyer", "offer", target),
                ("seller", "accept", target),
            ]
    return [
        ("buyer", "offer", opening),
        ("seller", "counter", target),
        ("buyer", "accept", target),
    ]


def _no_deal_turns(ask: int, buyer_max: int, seller_min: int) -> list[_Turn]:
    offer = _buyer_try(buyer_max, seller_min)
    counter = ask if ask not in (buyer_max, seller_min) and ask != offer else None
    turns: list[_Turn] = [("buyer", "offer", offer)]
    if counter is not None:
        turns.append(("seller", "counter", counter))
    turns.append(("buyer", "decline", None))
    return turns


def _buyer_try(buyer_max: int, seller_min: int) -> int | None:
    if buyer_max <= 1:
        return None
    offer = buyer_max - max(5, buyer_max // 10)
    if offer <= 0:
        return None
    if offer in (buyer_max, seller_min):
        offer -= 1
    if offer <= 0 or offer in (buyer_max, seller_min):
        return None
    return offer


def _inside(low: int, high: int, preferred: int) -> int:
    if low >= high:
        return low
    inner_low = low + 1
    inner_high = high - 1
    if inner_low <= inner_high:
        return min(max(preferred, inner_low), inner_high)
    return min(max(preferred, low), high)


def _texts(
    listing: ListingRecord,
    turns: list[_Turn],
    buyer_max: int,
    seller_min: int,
) -> list[str]:
    fallback = [_template(kind, amount, buyer_max, seller_min) for _speaker, kind, amount in turns]
    parsed = parse_json_reply(
        complete(
            _phrase_prompt(listing, turns),
            model=message_model(),
            effort=message_effort(),
            max_tokens=400,
        )
    )
    if not isinstance(parsed, dict):
        return fallback
    lines = parsed.get("messages")
    if not isinstance(lines, list) or len(lines) != len(turns):
        return fallback
    cleaned: list[str] = []
    for line in lines:
        if not isinstance(line, str):
            return fallback
        sentence = " ".join(line.split())
        if not sentence or len(sentence) > 240:
            return fallback
        if _mentions_limit(sentence, buyer_max, seller_min):
            return fallback
        lowered = sentence.lower()
        if "buyer_max" in lowered or "seller_min" in lowered or "price_limits" in lowered:
            return fallback
        cleaned.append(sentence)
    return cleaned


def _phrase_prompt(listing: ListingRecord, turns: list[_Turn]) -> str:
    lines: list[str] = []
    for index, (speaker, kind, amount) in enumerate(turns, start=1):
        if amount is None:
            lines.append(f"{index}. {speaker} {kind} with no dollar amount")
        else:
            lines.append(f"{index}. {speaker} {kind} {amount}")
    return (
        "Write one short sentence for each turn of a local pickup negotiation. "
        "Use only the dollar amounts listed below. "
        "Do not invent a budget, a private maximum, a private minimum, or any other price. "
        'Reply as JSON {"messages": ["...", "..."]} with one string per turn.\n'
        f"Title: {listing.title}\n"
        f"Category: {listing.category}\n"
        f"Asking price: {listing.price}\n"
        f"Neighborhood: {listing.neighborhood}\n"
        + "\n".join(lines)
    )


def _template(kind: str, amount: int | None, buyer_max: int, seller_min: int) -> str:
    if amount is None or _mentions_limit(str(amount), buyer_max, seller_min):
        if kind == "accept":
            return "That works. Pickup this week."
        if kind == "decline":
            return "I have to pass on that offer."
        if kind == "counter":
            return "I need a different number than that."
        return "I want this, but I can't meet the asking price."
    if kind == "accept":
        return f"That works at {amount}. Pickup this week."
    if kind == "decline":
        return "I have to pass on that offer."
    if kind == "counter":
        return f"I could meet you at {amount}."
    return f"I can do {amount} if I pick it up this week."


def _mentions_limit(text: str, buyer_max: int, seller_min: int) -> bool:
    for limit in (buyer_max, seller_min):
        raw = str(limit)
        if re.search(rf"(?<!\d){re.escape(raw)}(?!\d)", text):
            return True
        pretty = f"{limit:,}"
        if pretty != raw and pretty in text:
            return True
    return False
