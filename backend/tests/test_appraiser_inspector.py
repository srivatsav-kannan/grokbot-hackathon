"""Appraisal verdicts are computed in code. Inspection mixes heuristics with the model."""

from __future__ import annotations

import json

from backend.app.agents.appraiser import appraise, stub_appraise
from backend.app.agents.inspector import inspect, stub_inspect
from backend.app.repository import ListingRecord
from backend.app.schemas import Appraisal, Comp


def _listing(**overrides) -> ListingRecord:
    base = dict(
        id="lst_test",
        category="bikes",
        title="Aluminum road bike",
        description="Drop bars, two bottle mounts, and tires with tread left for city riding.",
        price=360,
        photos=["/placeholders/bike.svg"],
        neighborhood="Mission, San Francisco",
        source_url=None,
        posted_at="2026-11-19T18:30:00Z",
        origin="seed",
    )
    base.update(overrides)
    return ListingRecord(**base)


def _range() -> str:
    return json.dumps(
        {
            "estimated_value": 300,
            "low": 250,
            "high": 350,
            "verdict": "good_deal",
            "comps": [{"title": "Nearby road bike", "price": 310, "url": "https://example.com/comp"}],
        }
    )


def test_appraise_falls_back_to_stub_without_a_model(monkeypatch):
    monkeypatch.setattr("backend.app.agents.appraiser.complete", lambda *_args, **_kwargs: None)
    listing = _listing()
    assert appraise(listing) == stub_appraise(listing)


def test_appraise_rejects_invalid_json(monkeypatch):
    monkeypatch.setattr("backend.app.agents.appraiser.complete", lambda *_args, **_kwargs: "not json")
    listing = _listing()
    assert appraise(listing) == stub_appraise(listing)


def test_verdict_is_computed_from_the_range_not_the_model(monkeypatch):
    monkeypatch.setattr("backend.app.agents.appraiser.complete", lambda *_args, **_kwargs: _range())
    below = appraise(_listing(price=200))
    inside = appraise(_listing(price=300))
    above = appraise(_listing(price=400))
    assert (below.low, below.high, below.estimated_value) == (250, 350, 300)
    assert below.verdict == "good_deal"
    assert inside.verdict == "fair"
    assert above.verdict == "overpriced"
    assert below.comps[0].price == 310
    assert "buyer_max" not in below.model_dump()


def test_inspect_falls_back_to_stub_without_a_model(monkeypatch):
    monkeypatch.setattr("backend.app.agents.inspector.complete", lambda *_args, **_kwargs: None)
    listing = _listing(price=80)
    appraisal = stub_appraise(listing)
    assert inspect(listing, appraisal) == stub_inspect(listing, appraisal)
    assert inspect(listing, appraisal).trust_level == "low"


def test_inspect_merges_heuristics_with_model_signals(monkeypatch):
    def reply(prompt, *, image=None, timeout_s=8.0, **_extra):
        assert "11111" not in prompt
        assert "22222" not in prompt
        assert "buyer_max" not in prompt
        assert "seller_min" not in prompt
        return json.dumps(
            {
                "trust_level": "high",
                "signals": [{"code": "new_account", "reason": "The seller account was created today."}],
            }
        )

    monkeypatch.setattr("backend.app.agents.inspector.complete", reply)
    listing = _listing(
        price=40,
        description="Gift card only. Wire the deposit before we meet. Text me at the listing.",
        neighborhood="Bay Area",
        photos=["https://cdn.shutterstock.com/photo.jpg"],
    )
    appraisal = Appraisal(
        estimated_value=300,
        low=250,
        high=350,
        comps=[Comp(title="Comp", price=300, url="https://example.com/comp")],
        verdict="overpriced",
    )
    report = inspect(listing, appraisal)
    codes = {signal.code for signal in report.signals}
    assert "price_far_below_comps" in codes
    assert "gift_card" in codes
    assert "wire_transfer" in codes
    assert "cash_deposit" in codes
    assert "off_platform_contact" in codes
    assert "stock_photo" in codes
    assert "vague_location" in codes
    assert "new_account" in codes
    assert report.trust_level == "low"
    assert all(len(signal.reason.split(".")) >= 1 for signal in report.signals)


def test_clean_listing_stays_high_trust_when_the_model_agrees(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.inspector.complete",
        lambda *_args, **_kwargs: json.dumps({"trust_level": "high", "signals": []}),
    )
    listing = _listing()
    appraisal = stub_appraise(listing)
    report = inspect(listing, appraisal)
    assert report.trust_level == "high"
    assert report.signals == []


def test_inspector_calls_sonnet_unless_the_env_overrides_it(monkeypatch):
    seen: dict[str, str] = {}

    def capture(*_args, **kwargs):
        seen["model"] = kwargs.get("model", "")
        return None

    monkeypatch.setattr("backend.app.agents.inspector.complete", capture)
    monkeypatch.delenv("ANTHROPIC_INSPECTOR_MODEL", raising=False)
    listing = _listing()
    inspect(listing, stub_appraise(listing))
    assert seen["model"] == "claude-sonnet-5-5"

    monkeypatch.setenv("ANTHROPIC_INSPECTOR_MODEL", "claude-custom")
    inspect(listing, stub_appraise(listing))
    assert seen["model"] == "claude-custom"
