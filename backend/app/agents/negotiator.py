"""Buyer and Seller agents. Person B (@srivatsav-kannan) owns this file.

negotiate() runs a multi-round haggle in code. Each side knows only its own
bound: the buyer agent knows the buyer's private maximum, the seller agent knows
the seller's private minimum, and both see the public asking price.

- The buyer opens well under the asking price and concedes in shrinking steps,
  trying to close as low as it can. It never offers more than its maximum or
  more than the asking price.
- The seller counters down from the asking price in shrinking steps and never
  goes under its minimum.
- A deal closes when the offers meet or cross. The price is always inside
  [seller minimum, buyer maximum]. If the bounds don't overlap, the last round
  ends in a decline.

negotiate() must not log the bounds, return them as fields, or mention them in
message text. No visible amount ever equals either bound. The model only phrases
lines that code already priced. It never sees the bounds. Keep the signature.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from backend.app.agents.llm import complete, parse_json_reply
from backend.app.repository import ListingRecord
from backend.app.schemas import NegotiationMessage, Outcome

_Turn = tuple[str, str, int | None]

MAX_ROUNDS = 6
# Where the buyer opens, as a share of the most it is willing to pay.
_BUYER_OPEN = 0.6
# Cumulative share of the distance to each side's bound covered by round N.
# The steps shrink round over round, and both reach their bound on the last
# round so an overlap always closes.
_BUYER_PATH = (0.0, 0.32, 0.56, 0.74, 0.88, 1.0)
_SELLER_PATH = (0.18, 0.38, 0.56, 0.72, 0.87, 1.0)


@dataclass(frozen=True)
class NegotiationDraft:
    outcome: Outcome
    messages: list[NegotiationMessage]


def _at(offset_s: int) -> str:
    moment = datetime.now(timezone.utc) + timedelta(seconds=offset_s)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def negotiate(listing: ListingRecord, buyer_max: int, seller_min: int) -> NegotiationDraft:
    turns = _turns(listing.price, buyer_max, seller_min)
    texts = _texts(listing, turns, buyer_max, seller_min)
    return _draft(turns, texts)


def stub_negotiate(listing: ListingRecord, buyer_max: int, seller_min: int) -> NegotiationDraft:
    """Same rounds as negotiate(), template wording only. No model call."""

    turns = _turns(listing.price, buyer_max, seller_min)
    return _draft(turns, _fallback_texts(turns, buyer_max, seller_min))


def _draft(turns: list[_Turn], texts: list[str]) -> NegotiationDraft:
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
    outcome: Outcome = "deal" if turns and turns[-1][1] == "accept" else "no_deal"
    return NegotiationDraft(outcome=outcome, messages=messages)


def _turns(ask: int, buyer_max: int, seller_min: int) -> list[_Turn]:
    hidden = (buyer_max, seller_min)
    # Highest the buyer will offer: its max, never above the asking price.
    # One under the bound so the bound itself never shows in the transcript.
    buyer_cap = min(ask, buyer_max - 1)
    # Lowest the seller will go: one over its minimum, for the same reason.
    seller_floor = max(1, seller_min + 1)
    if buyer_cap < 1:
        return [("buyer", "decline", None)]

    buyer_open = _round_down(int(buyer_cap * _BUYER_OPEN))
    buyer_open = max(1, min(buyer_open, buyer_cap))
    if seller_floor > ask:
        # The seller won't take even its own asking price, so there is nothing
        # to counter with. Decline without putting a number on the table.
        return [("buyer", "offer", _dodge_down(buyer_open, hidden)), ("seller", "decline", None)]
    seller_start = ask
    standing = _dodge_up(seller_start, hidden)

    turns: list[_Turn] = []
    last_offer: int | None = None
    rounds = min(MAX_ROUNDS, len(_BUYER_PATH))
    for index in range(rounds):
        offer = buyer_open + (buyer_cap - buyer_open) * _BUYER_PATH[index]
        final = index == rounds - 1
        offer = buyer_cap if final else min(_round_down(int(offer)), buyer_cap)
        if last_offer is not None:
            offer = max(offer, last_offer)
        offer = _dodge_down(offer, hidden)
        if offer >= standing:
            # The seller's number is already within reach. Take it if the gap
            # is small or time is up; otherwise split the gap and keep pushing.
            floor_offer = last_offer if last_offer is not None else 0
            split = _dodge_down(_round_down(floor_offer + (standing - floor_offer) // 2), hidden)
            small_gap = standing - floor_offer <= max(5, ask // 50)
            if last_offer is None or small_gap or index == rounds - 1 or not (
                floor_offer < split < standing
            ):
                turns.append(("buyer", "accept", standing))
                return turns
            offer = split
        turns.append(("buyer", "offer", offer))
        last_offer = offer

        counter = seller_start - (seller_start - seller_floor) * _SELLER_PATH[index]
        counter = seller_floor if final else max(_round_up(int(round(counter))), seller_floor)
        counter = min(counter, standing)
        counter = _dodge_up(counter, hidden)
        if offer >= counter:
            turns.append(("seller", "accept", offer))
            return turns
        turns.append(("seller", "counter", counter))
        standing = counter

    if standing <= buyer_cap:
        turns.append(("buyer", "accept", standing))
    else:
        turns.append(("buyer", "decline", None))
    return turns


def _round_down(amount: int) -> int:
    if amount >= 100:
        return amount - amount % 5
    return amount


def _round_up(amount: int) -> int:
    if amount >= 100 and amount % 5:
        return amount + 5 - amount % 5
    return amount


def _dodge_down(amount: int, hidden: tuple[int, int]) -> int:
    while amount in hidden and amount > 1:
        amount -= 1
    return amount


def _dodge_up(amount: int, hidden: tuple[int, int]) -> int:
    while amount in hidden:
        amount += 1
    return amount


def _texts(
    listing: ListingRecord,
    turns: list[_Turn],
    buyer_max: int,
    seller_min: int,
) -> list[str]:
    fallback = _fallback_texts(turns, buyer_max, seller_min)
    parsed = parse_json_reply(complete(_phrase_prompt(listing, turns)))
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
        if _mentions_limit(sentence, buyer_max, seller_min) or _sounds_like_limit(sentence):
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
        "The buyer is trying to pay as little as possible; the seller is holding out "
        "for more. Each line should mention its dollar amount when it has one. "
        "Use only the dollar amounts listed below. "
        "Do not invent a budget, a private maximum, a private minimum, or any other price, "
        "and never say a number is someone's limit, max, minimum, or final price. "
        'Reply as JSON {"messages": ["...", "..."]} with one string per turn.\n'
        f"Title: {listing.title}\n"
        f"Category: {listing.category}\n"
        f"Asking price: {listing.price}\n"
        f"Neighborhood: {listing.neighborhood}\n"
        + "\n".join(lines)
    )


def _fallback_texts(turns: list[_Turn], buyer_max: int, seller_min: int) -> list[str]:
    texts: list[str] = []
    buyer_turn = 0
    seller_turn = 0
    for speaker, kind, amount in turns:
        if speaker == "buyer":
            texts.append(_template("buyer", kind, amount, buyer_turn, buyer_max, seller_min))
            buyer_turn += 1
        else:
            texts.append(_template("seller", kind, amount, seller_turn, buyer_max, seller_min))
            seller_turn += 1
    return texts


_BUYER_OFFERS = (
    "Would you take {amount}? I can pick it up this week.",
    "I can come up to {amount}.",
    "How about {amount}? Cash at pickup.",
    "Let me stretch to {amount}.",
    "{amount}, and I'll come to you.",
    "I can do {amount}.",
)
_SELLER_COUNTERS = (
    "It's in good shape. I could do {amount}.",
    "I can come down to {amount}.",
    "Meet me at {amount}?",
    "{amount} and it's yours.",
    "I could go to {amount}.",
    "{amount} is where I can be.",
)


def _template(
    speaker: str,
    kind: str,
    amount: int | None,
    turn: int,
    buyer_max: int,
    seller_min: int,
) -> str:
    if amount is not None and _mentions_limit(str(amount), buyer_max, seller_min):
        amount = None
    if kind == "accept":
        if amount is None:
            return "That works. Pickup this week."
        return f"Deal at {amount}. Pickup this week."
    if kind == "decline":
        if speaker == "buyer":
            return "We're too far apart. I'll pass for now."
        return "I have to pass on that offer."
    if amount is None:
        if kind == "counter":
            return "I need a different number than that."
        return "I want this, but I can't meet the asking price."
    pool = _SELLER_COUNTERS if kind == "counter" else _BUYER_OFFERS
    return pool[min(turn, len(pool) - 1)].format(amount=amount)


_LIMIT_WORDS = re.compile(
    r"(?i)\b(?:my|our|the|his|her|their)\s+(?:absolute\s+)?"
    r"(?:max|maximum|limit|ceiling|budget|floor|minimum|min|bottom\s+line|lowest|highest)\b"
)


def _sounds_like_limit(text: str) -> bool:
    return _LIMIT_WORDS.search(text) is not None


def _mentions_limit(text: str, buyer_max: int, seller_min: int) -> bool:
    for limit in (buyer_max, seller_min):
        raw = str(limit)
        if re.search(rf"(?<!\d){re.escape(raw)}(?!\d)", text):
            return True
        pretty = f"{limit:,}"
        if pretty != raw and pretty in text:
            return True
    return False
