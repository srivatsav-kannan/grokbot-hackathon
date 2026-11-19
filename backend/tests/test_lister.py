"""Photo drafts come from Claude vision, then the filename stub."""

from __future__ import annotations

import json

from backend.app.agents.lister import draft_from_photo, stub_draft_from_photo

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def test_draft_falls_back_to_the_filename_stub(monkeypatch):
    monkeypatch.setattr("backend.app.agents.lister.complete", lambda *_args, **_kwargs: None)
    draft = draft_from_photo(PNG, "desk.jpg")
    assert draft == stub_draft_from_photo(PNG, "desk.jpg")
    assert draft.category == "furniture"
    assert draft.title == "Oak desk"


def test_draft_uses_vision_json_and_passes_the_image(monkeypatch):
    seen: dict = {}

    def capture(prompt, *, image=None, timeout_s=8.0):
        seen["prompt"] = prompt
        seen["image"] = image
        return json.dumps(
            {
                "category": "bikes",
                "title": "City bike",
                "description": "Upright commuter with a rear rack, drafted from the photo.",
                "suggested_price": 240,
                "buyer_max": 99999,
            }
        )

    monkeypatch.setattr("backend.app.agents.lister.complete", capture)
    draft = draft_from_photo(PNG, "bike.png")
    assert seen["image"] == PNG
    assert "buyer_max" not in seen["prompt"]
    assert "seller_min" not in seen["prompt"]
    assert draft.category == "bikes"
    assert draft.title == "City bike"
    assert draft.suggested_price == 240
    assert "buyer_max" not in draft.model_dump()


def test_invalid_vision_json_uses_the_stub(monkeypatch):
    monkeypatch.setattr(
        "backend.app.agents.lister.complete",
        lambda *_args, **_kwargs: '{"category": "boats", "title": "", "suggested_price": 0}',
    )
    photo = PNG
    assert draft_from_photo(photo, "sofa.png") == stub_draft_from_photo(photo, "sofa.png")
