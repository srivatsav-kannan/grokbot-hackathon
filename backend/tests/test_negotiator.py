"""Offers are chosen in code. The model never sees the private bounds."""

from __future__ import annotations

import json
import re

from backend.app import repository as repo
from backend.app.agents.negotiator import negotiate
from backend.app.repository import ListingRecord


def _listing(**overrides) -> ListingRecord:
    base = dict(
        id="lst_test",
        category="bikes",
        title="Aluminum road bike",
        description="Drop bars and tires with tread left.",
        price=360,
        photos=["/placeholders/bike.svg"],
        neighborhood="Mission, San Francisco",
        source_url=None,
        posted_at="2026-11-19T18:30:00Z",
        origin="seed",
    )
    base.update(overrides)
    return ListingRecord(**base)


def _blob(draft) -> str:
    return json.dumps([message.model_dump() for message in draft.messages])


def test_deal_converges_inside_the_overlap_without_naming_limits(monkeypatch):
    prompts: list[str] = []

    def capture(prompt, *, image=None, timeout_s=8.0, **_extra):
        prompts.append(prompt)
        return None

    monkeypatch.setattr("backend.app.agents.negotiator.complete", capture)
    listing = _listing(price=360)
    draft = negotiate(listing, 500, 300)
    assert draft.outcome == "deal"
    assert len(draft.messages) >= 3
    assert draft.messages[0].from_ == "buyer"
    assert draft.messages[-1].kind == "accept"
    amounts = [message.amount for message in draft.messages]
    assert all(amount is not None for amount in amounts)
    buyer = [m.amount for m in draft.messages if m.from_ == "buyer" and m.kind == "offer"]
    seller = [m.amount for m in draft.messages if m.from_ == "seller" and m.kind == "counter"]
    # Several rounds: the buyer opens low and climbs, the seller comes down.
    assert len(buyer) >= 2 and len(seller) >= 1
    assert buyer == sorted(buyer)
    assert seller == sorted(seller, reverse=True)
    assert all(amount <= listing.price for amount in buyer)
    assert all(300 < amount <= listing.price for amount in seller)
    assert 300 < draft.messages[-1].amount < 500
    blob = _blob(draft)
    assert "500" not in prompts[0]
    assert "300" not in prompts[0]
    assert "buyer_max" not in prompts[0]
    assert "seller_min" not in prompts[0]
    for secret in ("500", "300", "buyer_max", "seller_min"):
        assert not re.search(rf"(?<!\d){secret}(?!\d)", blob)


def test_rounds_stay_inside_each_side_bound(monkeypatch):
    monkeypatch.setattr("backend.app.agents.negotiator.complete", lambda *_args, **_kwargs: None)
    for price, buyer_max, seller_min in ((620, 700, 400), (900, 650, 500), (280, 307, 241)):
        draft = negotiate(_listing(price=price), buyer_max, seller_min)
        assert draft.outcome == "deal"
        for message in draft.messages:
            if message.from_ == "buyer" and message.amount is not None:
                assert message.amount < buyer_max
            if message.from_ == "seller" and message.kind == "counter":
                assert message.amount > seller_min
        assert seller_min < draft.messages[-1].amount < buyer_max
        assert sum(1 for m in draft.messages if m.kind == "offer") >= 2


def test_no_overlap_ends_without_a_deal(monkeypatch):
    monkeypatch.setattr("backend.app.agents.negotiator.complete", lambda *_args, **_kwargs: None)
    draft = negotiate(_listing(price=620), 199, 510)
    assert draft.outcome == "no_deal"
    assert len(draft.messages) >= 2
    assert draft.messages[-1].kind == "decline"
    blob = _blob(draft)
    assert not re.search(r"(?<!\d)199(?!\d)", blob)
    assert not re.search(r"(?<!\d)510(?!\d)", blob)


def test_model_phrases_are_used_only_when_they_hide_the_limits(monkeypatch):
    def leak(prompt, *, image=None, timeout_s=8.0, **_extra):
        assert "11111" not in prompt
        assert "22222" not in prompt
        return json.dumps({"messages": ["My max is 22222.", "No."]})

    monkeypatch.setattr("backend.app.agents.negotiator.complete", leak)
    draft = negotiate(_listing(price=80), 11111, 22222)
    assert draft.outcome == "no_deal"
    blob = _blob(draft)
    assert "11111" not in blob
    assert "22222" not in blob
    assert "My max" not in blob

    def safe(prompt, *, image=None, timeout_s=8.0, **_extra):
        count = len(re.findall(r"(?m)^\d+\. ", prompt))
        lines = ["I can pick it up for that."] + ["Meet me at the public offer."] * (count - 1)
        return json.dumps({"messages": lines})

    monkeypatch.setattr("backend.app.agents.negotiator.complete", safe)
    agreed = negotiate(_listing(price=360), 500, 300)
    assert agreed.outcome == "deal"
    assert agreed.messages[0].text == "I can pick it up for that."
    assert 300 < agreed.messages[-1].amount < 500


def test_seed_transcripts_omit_stored_limits(client, monkeypatch):
    prompts: list[str] = []

    def capture(prompt, *, image=None, timeout_s=8.0, **_extra):
        prompts.append(prompt)
        return None

    monkeypatch.setattr("backend.app.agents.negotiator.complete", capture)
    ceilings = (401, 12345)
    for listing in repo.list_listings(None, None):
        limits = repo.get_limits(listing.id)
        assert limits is not None
        pairs = [(limits.buyer_max, limits.seller_min)]
        pairs.extend((ceiling, limits.seller_min) for ceiling in ceilings)
        for buyer_max, seller_min in pairs:
            draft = negotiate(listing, buyer_max, seller_min)
            blob = _blob(draft)
            for secret in (buyer_max, seller_min):
                assert secret not in _ints(draft)
                assert not re.search(rf"(?<!\d){secret}(?!\d)", blob)
            if buyer_max >= seller_min:
                assert draft.outcome == "deal"
                assert [message.amount for message in draft.messages if message.amount is not None]
            else:
                assert draft.outcome == "no_deal"
            for prompt in prompts:
                assert "buyer_max" not in prompt
                assert "seller_min" not in prompt
                for secret in (buyer_max, seller_min):
                    assert not re.search(rf"(?<!\d){secret}(?!\d)", prompt)
            prompts.clear()


def _ints(draft) -> set[int]:
    found: set[int] = set()

    def walk(node) -> None:
        if isinstance(node, bool):
            return
        if isinstance(node, int):
            found.add(node)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk([message.model_dump() for message in draft.messages])
    return found
