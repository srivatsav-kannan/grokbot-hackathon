"""Accounts, native ranking, external recommendations, and the background tick."""

from __future__ import annotations

import json

from backend.app.agents.appraiser import appraise
from backend.app.agents.inspector import inspect
from backend.app.repository import Limits, ListingRecord, insert_listing
from backend.app.services import run_background_tick
from backend.tests.conftest import sign_in


def _scouted_bike() -> None:
    listing = ListingRecord(
        id="lst_ext1",
        category="bikes",
        title="Scouted road bike",
        description="Public post from another marketplace.",
        price=250,
        photos=["https://example.com/bike.jpg"],
        neighborhood="Mission, San Francisco",
        source_url="https://sfbay.craigslist.org/bik/example.html",
        posted_at="2026-11-20T18:00:00Z",
        origin="scout",
    )
    appraisal = appraise(listing)
    insert_listing(
        listing,
        appraisal,
        inspect(listing, appraisal),
        Limits(buyer_max=240, seller_min=180),
    )


def test_missing_account_and_stale_session_say_so(client):
    missing = client.post(
        "/api/auth/login",
        json={"email": "gone@fairlot.test", "password": "fairlot-demo-pass"},
    )
    assert missing.status_code == 401
    assert missing.json()["error"]["message"] == "Account not found, please sign up again."

    created = sign_in(client)
    stale = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer ses_wiped-after-deploy"},
    )
    assert stale.status_code == 401
    assert stale.json()["error"]["message"] == "Account not found, please sign up again."
    assert created["email"]


def test_https_cookie_is_secure_and_lax(client):
    response = client.post(
        "/api/auth/signup",
        json={"email": "secure@fairlot.test", "password": "fairlot-demo-pass"},
        headers={"x-forwarded-proto": "https"},
    )
    assert response.status_code == 201
    cookie = response.headers["set-cookie"].lower()
    assert "samesite=lax" in cookie
    assert "secure" in cookie
    assert "httponly" in cookie


def test_signup_login_logout_and_bearer(client):
    created = sign_in(client)
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == created["id"]

    token = client.cookies["fairlot_session"]
    client.cookies.clear()
    missing = client.get("/api/auth/me")
    assert missing.status_code == 401
    bearer = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert bearer.status_code == 200
    assert bearer.json()["email"] == "ada@fairlot.test"

    logged_out = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logged_out.status_code == 204
    again = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert again.status_code == 401

    bad = client.post(
        "/api/auth/login",
        json={"email": "ada@fairlot.test", "password": "wrong-password"},
    )
    assert bad.status_code == 401
    ok = client.post(
        "/api/auth/login",
        json={"email": "ada@fairlot.test", "password": "fairlot-demo-pass"},
    )
    assert ok.status_code == 200

    duplicate = client.post(
        "/api/auth/signup",
        json={"email": "ada@fairlot.test", "password": "fairlot-demo-pass"},
    )
    assert duplicate.status_code == 400


def test_native_ranks_above_scouted_and_external_is_a_message(client):
    _scouted_bike()
    listed = client.get("/api/listings", params={"category": "bikes"})
    ids = [row["id"] for row in listed.json()["listings"]]
    assert ids[-1] == "lst_ext1"
    assert listed.json()["listings"][-1]["source_name"] == "Craigslist"
    assert all(row["origin"] != "scout" for row in listed.json()["listings"][:-1])

    external = client.get("/api/listings", params={"kind": "external"})
    assert [row["id"] for row in external.json()["listings"]] == ["lst_ext1"]
    native = client.get("/api/listings", params={"kind": "native"})
    assert native.json()["listings"] == []

    sign_in(client)
    created = client.post(
        "/api/wants",
        json={"text": "road bike under $400 in SF", "category": "bikes"},
    )
    token = created.json()["access_token"]
    want_id = created.json()["id"]
    targeted = client.post(
        f"/api/wants/{want_id}/target",
        headers={"Authorization": f"Bearer {token}"},
        json={"listing_id": "lst_ext1"},
    )
    assert targeted.status_code == 200
    body = targeted.json()
    assert body["recommendations"]
    advice = body["recommendations"][0]
    assert advice["listing_id"] == "lst_ext1"
    assert advice["source_name"] == "Craigslist"
    assert advice["source_url"].startswith("https://sfbay.craigslist.org/")
    assert "$250" in advice["message"]
    assert all(item["listing_id"] != "lst_ext1" for item in body["negotiations"])
    blob = json.dumps(body)
    assert "180" not in blob
    assert "240" not in blob
    assert "buyer_max" not in blob
    assert "seller_min" not in blob


def test_same_buyer_bot_text_returns_the_existing_want(client):
    sign_in(client)
    first = client.post("/api/wants", json={"text": "Road bike under $400 in SF", "category": "bikes"})
    second = client.post("/api/wants", json={"text": "  road bike under $400 in sf  ", "category": "bikes"})
    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["access_token"] != first.json()["access_token"]


def test_background_tick_is_idempotent(client):
    sign_in(client)
    created = client.post(
        "/api/wants",
        json={"text": "road bike under $400 in SF", "category": "bikes", "area": "San Francisco"},
    )
    token = created.json()["access_token"]
    want_id = created.json()["id"]
    hunted = client.post(f"/api/wants/{want_id}/hunt", headers={"Authorization": f"Bearer {token}"})
    assert hunted.status_code == 200
    before = [item["id"] for item in hunted.json()["negotiations"]]
    assert before
    run_background_tick()
    run_background_tick()
    after = client.get(f"/api/wants/{want_id}", headers={"Authorization": f"Bearer {token}"})
    assert [item["id"] for item in after.json()["negotiations"]] == before
    activity = json.dumps(client.get("/api/activity").json())
    for secret in ("buyer_max", "seller_min", "price_limits", "access_token", "400"):
        assert secret not in activity
