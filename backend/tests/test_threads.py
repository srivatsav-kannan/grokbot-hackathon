"""Threads keep each side's private limit on that side of the wire."""

from __future__ import annotations

import json

from backend.tests.conftest import sign_in


def test_limits_are_visible_only_to_their_owner(client):
    sign_in(client, email="seller-thread@fairlot.test")
    published = client.post(
        "/api/listings",
        json={
            "category": "furniture",
            "title": "Oak stool",
            "description": "A sturdy stool with a worn finish and four even legs.",
            "price": 180,
            "photos": ["/placeholders/furniture.svg"],
            "neighborhood": "Mission, San Francisco",
            "minimum": 34343,
        },
    )
    assert published.status_code == 201
    listing_id = published.json()["id"]
    assert "34343" not in json.dumps(published.json())

    client.cookies.clear()
    sign_in(client, email="buyer-thread@fairlot.test")
    opened = client.post(
        "/api/threads",
        json={
            "listing_id": listing_id,
            "intent": "offer",
            "amount": 200,
            "limit": 45454,
            "text": "I can pick it up Saturday.",
        },
    )
    assert opened.status_code == 201
    buyer = opened.json()
    assert buyer["my_limit"] == 45454
    assert buyer["role"] == "buyer"
    without = dict(buyer)
    without.pop("my_limit")
    assert "45454" not in json.dumps(without)
    assert "34343" not in json.dumps(buyer)

    client.cookies.clear()
    logged_in = client.post(
        "/api/auth/login",
        json={"email": "seller-thread@fairlot.test", "password": "fairlot-demo-pass"},
    )
    assert logged_in.status_code == 200
    seen = client.get(f"/api/threads/{buyer['id']}")
    assert seen.status_code == 200
    seller = seen.json()
    assert seller["role"] == "seller"
    assert seller["my_limit"] == 34343
    assert "45454" not in json.dumps(seller)
    inbox = client.get("/api/deals")
    assert inbox.status_code == 200
    assert "34343" not in json.dumps(inbox.json())
    assert "45454" not in json.dumps(inbox.json())
    activity = json.dumps(client.get("/api/activity").json())
    assert "34343" not in activity
    assert "45454" not in activity


def test_accept_records_one_sale(client):
    sign_in(client, email="seller-sale@fairlot.test")
    published = client.post(
        "/api/listings",
        json={
            "category": "bikes",
            "title": "City bike",
            "description": "A city bike with working brakes and a rear rack.",
            "price": 220,
            "photos": ["/placeholders/bike.svg"],
            "neighborhood": "Oakland",
            "minimum": 150,
        },
    )
    listing_id = published.json()["id"]
    client.cookies.clear()
    sign_in(client, email="buyer-sale@fairlot.test")
    opened = client.post(
        "/api/threads",
        json={"listing_id": listing_id, "intent": "offer", "amount": 200, "text": "I can offer 200."},
        headers={"Idempotency-Key": "offer-1"},
    )
    again = client.post(
        "/api/threads",
        json={"listing_id": listing_id, "intent": "offer", "amount": 200, "text": "I can offer 200."},
        headers={"Idempotency-Key": "offer-1"},
    )
    assert again.json()["id"] == opened.json()["id"]
    assert len(again.json()["messages"]) == len(opened.json()["messages"])
    client.cookies.clear()
    client.post("/api/auth/login", json={"email": "seller-sale@fairlot.test", "password": "fairlot-demo-pass"})
    accepted = client.post(
        f"/api/threads/{opened.json()['id']}/messages",
        json={"kind": "accept", "text": "I'll take 200.", "amount": 200},
    )
    assert accepted.status_code == 200
    repeat = client.post(
        f"/api/threads/{opened.json()['id']}/messages",
        json={"kind": "accept", "text": "I'll take 200.", "amount": 200},
    )
    assert len(repeat.json()["messages"]) == len(accepted.json()["messages"])
    listing = client.get(f"/api/listings/{listing_id}")
    assert listing.json()["sold_for"] == 200


def test_buyer_bot_shows_in_deals(client):
    sign_in(client, email="bot-buyer@fairlot.test")
    created = client.post("/api/wants", json={"text": "red road bike"})
    assert created.status_code == 201
    inbox = client.get("/api/deals")
    labels = [bot["label"] for bot in inbox.json()["buyer_bots"]]
    assert "red road bike" in labels
