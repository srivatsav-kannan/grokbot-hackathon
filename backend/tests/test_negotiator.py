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

    def capture(prompt, *, image=None, timeout_s=8.0):
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
    assert all(amount is not None and 300 < amount < 500 for amount in amounts)
    assert amounts == sorted(amounts)
    blob = _blob(draft)
    assert "500" not in prompts[0]
    assert "300" not in prompts[0]
    assert "buyer_max" not in prompts[0]
    assert "seller_min" not in prompts[0]
    for secret in ("500", "300", "buyer_max", "seller_min"):
        assert not re.search(rf"(?<!\d){secret}(?!\d)", blob)


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
    def leak(prompt, *, image=None, timeout_s=8.0):
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

    def safe(prompt, *, image=None, timeout_s=8.0):
        return json.dumps(
            {
                "messages": [
                    "I can pick it up for that.",
                    "Meet me at the public offer.",
                    "Yes, pickup tomorrow.",
                ]
            }
        )

    monkeypatch.setattr("backend.app.agents.negotiator.complete", safe)
    agreed = negotiate(_listing(price=360), 500, 300)
    assert agreed.messages[0].text == "I can pick it up for that."
    assert all(300 < message.amount < 500 for message in agreed.messages)


def test_seed_transcripts_omit_stored_limits(client, monkeypatch):
    prompts: list[str] = []

    def capture(prompt, *, image=None, timeout_s=8.0):
        prompts.append(prompt)
        return None

    monkeypatch.setattr("backend.app.agents.negotiator.complete", capture)
    ceilings = (400, 12345)
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
    joined = "\n".join(prompts)
    assert "buyer_max" not in joined
    assert "seller_min" not in joined
    for secret in (400, 12345):
        assert not re.search(rf"(?<!\d){secret}(?!\d)", joined)


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
