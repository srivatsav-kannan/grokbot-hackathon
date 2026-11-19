"""Private ceilings, seller floors, and want tokens stay off the wire.

Allowed exception: POST /api/wants returns access_token once, to the creator.
OpenAPI may name that response field and the request field max_price.
Examples, and every other response, must not carry those names or the stored secrets.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from backend.app.agents.appraiser import appraise
from backend.app.agents.buyer import match_listings, parse_want, private_max_from_text
from backend.app.agents.inspector import inspect
from backend.app.agents.lister import draft_from_photo
from backend.app.agents.negotiator import negotiate
from backend.app.db import connect
from backend.app.repository import get_listing

FORBIDDEN_KEYS = {"buyer_max", "seller_min", "price_limits", "max_price"}
TOKEN_KEY = "access_token"
EXAMPLE_KEYS = {"example", "examples"}


def _walk_keys(node, found: set[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            found.add(str(key))
            _walk_keys(value, found)
    elif isinstance(node, list):
        for item in node:
            _walk_keys(item, found)


def _walk_ints(node, found: set[int]) -> None:
    if isinstance(node, bool):
        return
    if isinstance(node, int):
        found.add(node)
    elif isinstance(node, dict):
        for value in node.values():
            _walk_ints(value, found)
    elif isinstance(node, list):
        for item in node:
            _walk_ints(item, found)


def _assert_public(payload, *, token: str | None = None, allow_token_field: bool = False) -> None:
    keys: set[str] = set()
    _walk_keys(payload, keys)
    leaked = keys & FORBIDDEN_KEYS
    assert not leaked, f"private field in response: {sorted(leaked)}"
    if allow_token_field:
        assert TOKEN_KEY in keys
    else:
        assert TOKEN_KEY not in keys
    if token:
        assert token not in json.dumps(payload)
    secrets = _secret_numbers()
    present = set()
    _walk_ints(payload, present)
    leaked_numbers = secrets & present
    assert not leaked_numbers, "stored private number appeared in a response"


def _secret_numbers() -> set[int]:
    with connect() as conn:
        limits = conn.execute("SELECT buyer_max, seller_min FROM price_limits").fetchall()
    numbers: set[int] = set()
    for row in limits:
        if row["buyer_max"] is not None:
            numbers.add(int(row["buyer_max"]))
        if row["seller_min"] is not None:
            numbers.add(int(row["seller_min"]))
    return numbers


def _examples(node, found: list) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in EXAMPLE_KEYS:
                found.append(value)
            else:
                _examples(value, found)
    elif isinstance(node, list):
        for item in node:
            _examples(item, found)


def test_responses_and_openapi_hide_private_fields(client):
    created = client.post(
        "/api/wants",
        json={"text": "road bike under $12345 in SF", "category": "bikes"},
    )
    assert created.status_code == 201
    body = created.json()
    token = body["access_token"]
    want_id = body["id"]
    _assert_public(body, allow_token_field=True)
    assert "12345" not in json.dumps({k: v for k, v in body.items() if k != TOKEN_KEY})

    listing_id = client.get("/api/listings").json()["listings"][0]["id"]
    payloads = [
        client.get("/api/listings").json(),
        client.get("/api/listings/lst_02").json(),
        client.post("/api/negotiations", json={"listing_id": "lst_01", "buyer_max": 1, "seller_min": 2}).json(),
        client.get(f"/api/wants/{want_id}", headers={"Authorization": f"Bearer {token}"}).json(),
        client.post(f"/api/wants/{want_id}/hunt", headers={"Authorization": f"Bearer {token}"}).json(),
        client.post(
            f"/api/wants/{want_id}/target",
            headers={"Authorization": f"Bearer {token}"},
            json={"listing_id": listing_id, "max_price": 12345},
        ).json(),
    ]
    negotiation_id = payloads[2]["id"]
    payloads.append(client.get(f"/api/negotiations/{negotiation_id}").json())
    payloads.append(client.post("/api/scout/run", json={"categories": ["bikes"]}).json())

    for payload in payloads:
        _assert_public(payload, token=token, allow_token_field=False)

    schema = client.get("/openapi.json").json()
    schema_keys: set[str] = set()
    _walk_keys(schema, schema_keys)
    assert not (schema_keys & {"buyer_max", "seller_min", "price_limits"})
    examples: list = []
    _examples(schema, examples)
    blob = json.dumps(examples).lower()
    for forbidden in ("buyer_max", "seller_min", "price_limits", "max_price", "access_token"):
        assert forbidden not in blob
    assert token not in json.dumps(schema)
    assert "12345" not in json.dumps(schema)


def test_agent_prompts_and_transcripts_omit_private_limits(client, monkeypatch):
    """complete() prompts and negotiation text must not carry the hidden bounds."""

    buyer_max = 11111
    seller_min = 22222
    prompts: list[str] = []

    def capture(prompt, *, image=None, timeout_s=8.0):
        prompts.append(prompt)
        return None

    for module in ("appraiser", "inspector", "buyer", "negotiator", "lister"):
        monkeypatch.setattr(f"backend.app.agents.{module}.complete", capture)

    text = "road bike under $11111 in SF"
    assert private_max_from_text(text) == buyer_max
    criteria = parse_want(text)
    assert "11111" not in json.dumps(asdict(criteria))
    assert "buyer_max" not in json.dumps(asdict(criteria))
    match_listings(criteria)

    listing = get_listing("lst_02")
    assert listing is not None
    appraisal = appraise(listing)
    inspect(listing, appraisal)
    draft_from_photo(b"\x89PNG\r\n\x1a\n", "bike.png")
    for limits in ((buyer_max, seller_min), (seller_min, buyer_max)):
        draft = negotiate(listing, limits[0], limits[1])
        transcript = json.dumps([message.model_dump() for message in draft.messages])
        assert "11111" not in transcript
        assert "22222" not in transcript
        assert "buyer_max" not in transcript
        assert "seller_min" not in transcript

    blob = "\n".join(prompts)
    for secret in ("11111", "22222", "buyer_max", "seller_min", "price_limits"):
        assert secret not in blob
