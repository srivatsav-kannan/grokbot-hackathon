"""Want criteria stay public. The private max is a separate extraction."""

from __future__ import annotations

import json
from dataclasses import asdict, fields

from backend.app.agents.buyer import (
    WantCriteria,
    match_listings,
    parse_want,
    private_max_from_text,
    stub_parse_want,
)


def test_want_criteria_has_no_price_field():
    names = {field.name for field in fields(WantCriteria)}
    assert names == {"category", "area", "keywords"}


def test_private_max_patterns_do_not_land_on_the_criteria():
    cases = {
        "road bike under $400 in SF": 400,
        "road bike under $12345 in SF": 12345,
        "laptop budget of $1,200": 1200,
        "desk up to 250": 250,
        "monitor no more than $80": 80,
        "bike $500 max": 500,
        "oak desk": None,
        "bike over $400": None,
    }
    for text, expected in cases.items():
        assert private_max_from_text(text) == expected
        dumped = json.dumps(asdict(stub_parse_want(text)))
        if expected is not None:
            assert str(expected) not in dumped
            assert f"{expected:,}" not in dumped


def test_parse_want_redacts_the_ceiling_before_the_model(monkeypatch):
    prompts: list[str] = []

    def capture(prompt, *, image=None, timeout_s=8.0):
        prompts.append(prompt)
        return json.dumps(
            {
                "category": "bikes",
                "area": "SF",
                "keywords": ["road", "4321", "budget"],
                "max_price": 4321,
                "buyer_max": 4321,
            }
        )

    monkeypatch.setattr("backend.app.agents.buyer.complete", capture)
    criteria = parse_want("road bike under $4321 in SF")
    assert "4321" not in prompts[0]
    assert "buyer_max" not in prompts[0]
    assert criteria.category == "bikes"
    assert criteria.area == "San Francisco"
    assert "road" in criteria.keywords
    assert "4321" not in criteria.keywords
    assert "budget" not in criteria.keywords
    assert "4321" not in json.dumps(asdict(criteria))


def test_parse_want_falls_back_when_the_model_is_unusable(monkeypatch):
    monkeypatch.setattr("backend.app.agents.buyer.complete", lambda *_args, **_kwargs: "nope")
    text = "road bike under $400 in SF"
    assert parse_want(text) == stub_parse_want(text)


def test_road_bike_in_san_francisco_ranks_first(client):
    criteria = parse_want("road bike under $400 in SF")
    assert criteria.category == "bikes"
    assert criteria.area == "San Francisco"
    assert any("road" in word for word in criteria.keywords)
    matches = match_listings(criteria)
    assert matches
    assert matches[0].listing_id == "lst_06"
    assert matches == sorted(matches, key=lambda item: (-item.score, item.listing_id))
    assert all(0 < item.score <= 1 for item in matches)


def test_desk_query_prefers_the_mission_desk(client):
    criteria = parse_want("oak desk in the mission")
    assert criteria.category == "furniture"
    assert criteria.area == "Mission"
    assert "desk" in criteria.keywords
    matches = match_listings(criteria)
    assert matches[0].listing_id == "lst_16"


def test_model_notes_replace_reasons_without_reordering(client, monkeypatch):
    def capture(prompt, *, image=None, timeout_s=8.0):
        assert "11111" not in prompt
        assert "buyer_max" not in prompt
        return json.dumps(
            {"notes": [{"listing_id": "lst_06", "reason": "Road bike in San Francisco."}]}
        )

    monkeypatch.setattr("backend.app.agents.buyer.complete", capture)
    criteria = WantCriteria(category="bikes", area="San Francisco", keywords=["road"])
    matches = match_listings(criteria)
    assert matches[0].listing_id == "lst_06"
    assert matches[0].reason == "Road bike in San Francisco."
