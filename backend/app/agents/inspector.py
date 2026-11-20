"""Inspector. Person B (@srivatsav-kannan) owns this file.

Replace stub_inspect. Keep inspect(). Reasons are one plain sentence each.
Inspector is global: it does not take a user id or a private price limit.
"""

from __future__ import annotations

import os
import re

from backend.app.agents.llm import complete, parse_json_reply
from backend.app.repository import ListingRecord
from backend.app.schemas import Appraisal, Inspection, Signal

_SEVERE = {
    "price_far_below_comps",
    "gift_card",
    "wire_transfer",
    "cash_deposit",
    "off_platform_contact",
    "stock_photo",
    "payment_before_meetup",
}

_CODE_ALIASES = {
    "wire": "wire_transfer",
    "wiring": "wire_transfer",
    "giftcard": "gift_card",
    "gift_cards": "gift_card",
    "deposit": "cash_deposit",
    "offplatform": "off_platform_contact",
    "off_platform": "off_platform_contact",
    "stock": "stock_photo",
    "vague": "vague_location",
    "vague_area": "vague_location",
    "price_too_low": "price_far_below_comps",
}

_CODE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
_GIFT_CARD = re.compile(r"(?i)\bgift\s*cards?\b")
_WIRE = re.compile(
    r"(?i)\bwire\b(?!\s+wheel)|\b(?:western union|moneygram|wiring)\b|\b(?:bitcoin|btc|crypto|usdt|ethereum)\b"
)
_DEPOSIT = re.compile(r"(?i)\b(?:deposit|holding fee)\b")
_OFF_PLATFORM = re.compile(
    r"(?i)\b(?:whatsapp|telegram|wechat|kik|gmail|yahoo|hotmail|outlook|venmo|zelle|paypal)\b"
    r"|\bcash\s*app\b|\b(?:text|email|call|dm) me\b|\bon signal\b|\bsignal app\b"
    r"|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"
)
_PAY_FIRST = re.compile(
    r"(?i)(?:\b(?:pay|payment|send money)\b.{0,40}\b(?:before|first|upfront|up front)\b)"
    r"|\b(?:shipping only|no meetup|cannot meet|won't meet|will not meet)\b"
)
_STOCK_TEXT = re.compile(r"(?i)\b(?:stock photo|catalog photo|promotional image|shutterstock|getty images|istock)\b")
_STOCK_URL = ("shutterstock", "gettyimages", "istockphoto")
_VAGUE_AREAS = {
    "",
    "bay area",
    "sf bay",
    "sf bay area",
    "san francisco bay area",
    "california",
    "ca",
    "somewhere",
    "nearby",
    "tbd",
    "n/a",
    "na",
    "unknown",
    "anywhere",
}
_TRUST_RANK = {"high": 0, "medium": 1, "low": 2}


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


def inspector_model() -> str:
    return os.environ.get("ANTHROPIC_INSPECTOR_MODEL", "").strip() or "claude-sonnet-5-5"


def inspect(listing: ListingRecord, appraisal: Appraisal) -> Inspection:
    parsed = parse_json_reply(
        complete(_inspection_prompt(listing, appraisal), model=inspector_model())
    )
    if not isinstance(parsed, dict) or not isinstance(parsed.get("signals"), list):
        return stub_inspect(listing, appraisal)
    signals = _merge_signals(listing, appraisal, parsed.get("signals"))
    trust = _trust_for(signals)
    model_trust = parsed.get("trust_level")
    if isinstance(model_trust, str) and model_trust in _TRUST_RANK:
        if _TRUST_RANK[model_trust] > _TRUST_RANK[trust]:
            trust = model_trust
    return Inspection(trust_level=trust, signals=signals)  # type: ignore[arg-type]


def _inspection_prompt(listing: ListingRecord, appraisal: Appraisal) -> str:
    return (
        "You check one SF Bay Area classifieds listing for scam signals. "
        "Reply with one JSON object only, no markdown: "
        '{"trust_level": "high", "signals": [{"code": "snake_case", "reason": "One plain sentence."}]}. '
        "trust_level is high, medium, or low. "
        "Flag a price far below the comparable range, a request for a deposit, wire, gift card, or crypto, "
        "payment before meeting, contact off the listing, stock photos, and a vague location. "
        "Use an empty signals list when nothing looks wrong. "
        "Do not mention a buyer maximum or a seller minimum.\n"
        f"Category: {listing.category}\n"
        f"Title: {listing.title}\n"
        f"Description: {listing.description}\n"
        f"Neighborhood: {listing.neighborhood}\n"
        f"Asking price: {listing.price}\n"
        f"Comparable low: {appraisal.low}\n"
        f"Comparable high: {appraisal.high}\n"
        f"Estimated value: {appraisal.estimated_value}"
    )


def _merge_signals(listing: ListingRecord, appraisal: Appraisal, model_signals: list) -> list[Signal]:
    merged: list[Signal] = []
    seen: set[str] = set()
    for signal in _heuristic_signals(listing, appraisal):
        merged.append(signal)
        seen.add(signal.code)
    for signal in _model_signals(model_signals):
        if signal.code in seen:
            continue
        merged.append(signal)
        seen.add(signal.code)
    return merged


def _heuristic_signals(listing: ListingRecord, appraisal: Appraisal) -> list[Signal]:
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
    text = f"{listing.title}\n{listing.description}"
    if _GIFT_CARD.search(text):
        signals.append(Signal(code="gift_card", reason="The seller asks to be paid with a gift card."))
    if _WIRE.search(text):
        signals.append(Signal(code="wire_transfer", reason="The seller asks for a wire transfer or cryptocurrency."))
    if _DEPOSIT.search(text):
        signals.append(Signal(code="cash_deposit", reason="The seller asks for a deposit before you can see the item."))
    if _OFF_PLATFORM.search(text):
        signals.append(Signal(code="off_platform_contact", reason="The seller wants to continue the conversation off the listing."))
    if _PAY_FIRST.search(text):
        signals.append(Signal(code="payment_before_meetup", reason="The seller wants payment before an in-person meetup."))
    photos = " ".join(listing.photos).lower()
    if _STOCK_TEXT.search(text) or any(host in photos for host in _STOCK_URL):
        signals.append(Signal(code="stock_photo", reason="The photos look like stock or catalog images."))
    if listing.neighborhood.strip().lower() in _VAGUE_AREAS:
        signals.append(Signal(code="vague_location", reason="The location is too vague to plan a local pickup."))
    return signals


def _model_signals(raw: list) -> list[Signal]:
    signals: list[Signal] = []
    for item in raw[:8]:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        reason = item.get("reason")
        if not isinstance(code, str) or not isinstance(reason, str):
            continue
        normalized = _CODE_ALIASES.get(code.strip().lower(), code.strip().lower())
        sentence = " ".join(reason.split())
        if not _CODE.fullmatch(normalized) or not sentence:
            continue
        signals.append(Signal(code=normalized, reason=sentence[:240]))
    return signals


def _trust_for(signals: list[Signal]) -> str:
    if any(signal.code in _SEVERE for signal in signals):
        return "low"
    if signals:
        return "medium"
    return "high"
