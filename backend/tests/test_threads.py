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


def test_bot_agreement_waits_for_buyer_approval_then_records_one_sale(client):
    sign_in(client, email="approve-buyer@fairlot.test")
    opened = client.post("/api/threads", json={"listing_id": "lst_02", "intent": "bot", "limit": 260})
    assert opened.status_code == 201
    thread = opened.json()
    assert thread["status"] == "agreed"
    assert thread["summary"].startswith("Bot agreed")
    assert client.get("/api/deals").json()["completed"] == []

    price = [m["amount"] for m in thread["messages"] if m["amount"] is not None][-1]
    for key in ("approve-1", "approve-2"):
        approved = client.post(
            f"/api/threads/{thread['id']}/messages",
            json={"kind": "accept", "amount": price, "text": "Approved."},
            headers={"Idempotency-Key": key},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "deal"
    completed = client.get("/api/deals").json()["completed"]
    assert len(completed) == 1
    assert completed[0]["price"] == price
    assert client.get("/api/listings/lst_02").json()["sold_for"] == price


def test_switching_on_the_buyer_bot_mid_thread_runs_to_an_end(client):
    sign_in(client, email="toggle-buyer@fairlot.test")
    opened = client.post(
        "/api/threads",
        json={"listing_id": "lst_14", "intent": "offer", "amount": 400, "limit": 640},
    ).json()
    assert opened["status"] == "open"
    toggled = client.post(f"/api/threads/{opened['id']}/mode", json={"mode": "bot"}).json()
    assert toggled["buyer_mode"] == "bot"
    assert toggled["status"] in {"agreed", "declined"}
    amounts = [m["amount"] for m in toggled["messages"] if m["amount"] is not None]
    assert all(a <= 640 for a in amounts if a)
    assert "640" not in " ".join(m["text"] for m in toggled["messages"])


def test_bots_too_far_apart_pass_instead_of_looping(client):
    sign_in(client, email="lowball@fairlot.test")
    opened = client.post(
        "/api/threads",
        json={"listing_id": "lst_14", "intent": "offer", "amount": 100, "limit": 151},
    ).json()
    toggled = client.post(f"/api/threads/{opened['id']}/mode", json={"mode": "bot"}).json()
    assert toggled["status"] == "declined"
    assert len(toggled["messages"]) < 20


def test_demo_seller_can_hand_the_waiting_offer_to_its_bot(client):
    login = client.post("/api/auth/login", json={"email": "demo@fairlot.app", "password": "fairlot-demo"})
    assert login.status_code == 200
    inbox = client.get("/api/deals").json()
    waiting = inbox["listings"][0]["threads"][0]
    assert waiting["summary"] == "Waiting on you"
    done = client.post(f"/api/threads/{waiting['id']}/mode", json={"mode": "bot"}).json()
    assert done["status"] in {"deal", "declined"}
    if done["status"] == "deal":
        assert client.get("/api/deals").json()["completed"][0]["role"] == "seller"
