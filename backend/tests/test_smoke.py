"""Every public endpoint responds and the want flow runs on stubs."""

from __future__ import annotations

from backend.tests.conftest import sign_in

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_health(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert health.json()["database"] in {"sqlite", "postgres"}


def test_feed_detail_and_badges(client):
    listed = client.get("/api/listings")
    assert listed.status_code == 200
    rows = listed.json()["listings"]
    assert len(rows) == 12
    assert {row["origin"] for row in rows} == {"seed"}
    assert {row["category"] for row in rows} == {"bikes", "computers", "furniture"}
    for row in rows:
        assert row["appraisal"]["verdict"] in {"good_deal", "fair", "overpriced"}
        assert row["inspection"]["trust_level"] in {"high", "medium", "low"}
        assert "description" not in row

    bikes = client.get("/api/listings", params={"category": "bikes", "q": "road"})
    assert bikes.status_code == 200
    assert [row["id"] for row in bikes.json()["listings"]] == ["lst_02"]

    detail = client.get("/api/listings/lst_09")
    assert detail.status_code == 200
    body = detail.json()
    assert body["appraisal"]["comps"]
    assert body["inspection"]["signals"]
    assert body["inspection"]["trust_level"] == "low"

    missing = client.get("/api/listings/lst_missing")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_lister_publish_negotiate_and_scout(client):
    sign_in(client)
    drafted = client.post(
        "/api/lister",
        files={"photo": ("desk.jpg", PNG, "image/png")},
    )
    assert drafted.status_code == 200
    draft = drafted.json()["draft"]
    assert draft["category"] == "furniture"
    assert isinstance(draft["suggested_price"], int)

    published = client.post(
        "/api/listings",
        json={
            "category": draft["category"],
            "title": draft["title"],
            "description": draft["description"],
            "price": draft["suggested_price"],
            "photos": ["/placeholders/furniture.svg"],
            "neighborhood": "Mission, San Francisco",
        },
    )
    assert published.status_code == 201
    listing = published.json()
    assert listing["origin"] == "lister"
    assert listing["source_name"] == "Fairlot"
    assert "minimum" not in listing
    assert listing["appraisal"]["verdict"] in {"good_deal", "fair", "overpriced"}

    photo = client.get("/placeholders/bike.svg")
    assert photo.status_code == 200

    client.cookies.clear()
    locked = client.post("/api/negotiations", json={"listing_id": "lst_01"})
    assert locked.status_code == 401
    sign_in(client, email="buyer@fairlot.test")

    deal = client.post("/api/negotiations", json={"listing_id": "lst_01"})
    assert deal.status_code == 201
    assert deal.json()["outcome"] == "deal"
    assert deal.json()["accepted"] is False
    assert deal.json()["messages"][0]["from"] == "buyer"
    accepted = client.post(f"/api/negotiations/{deal.json()['id']}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["accepted"] is True

    no_deal = client.post("/api/negotiations", json={"listing_id": "lst_03"})
    assert no_deal.status_code == 201
    assert no_deal.json()["outcome"] == "no_deal"
    fetched = client.get(f"/api/negotiations/{no_deal.json()['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["outcome"] == "no_deal"

    scout = client.post("/api/scout/run", json={"categories": ["bikes", "computers", "furniture"]})
    assert scout.status_code == 200
    report = scout.json()
    assert report["stopped"] is False
    assert report["added"] == 0
    assert report["cached"] >= 12
    assert report["report"] is None


def test_want_hunt_and_target(client):
    sign_in(client)
    created = client.post(
        "/api/wants",
        json={"text": "road bike under $400 in SF", "category": "bikes", "area": "San Francisco"},
    )
    assert created.status_code == 201
    token = created.json()["access_token"]
    want_id = created.json()["id"]
    assert created.json()["status"] == "open"
    headers = {"Authorization": f"Bearer {token}"}

    viewed = client.get(f"/api/wants/{want_id}", headers=headers)
    assert viewed.status_code == 200
    want = viewed.json()
    assert want["status"] == "open"
    assert want["criteria"]["category"] == "bikes"
    assert want["criteria"]["area"] == "San Francisco"
    assert any("road" in word for word in want["criteria"]["keywords"])
    assert want["matches"] == []
    assert "access_token" not in want

    denied = client.get(f"/api/wants/{want_id}", headers={"Authorization": "Bearer tok_wrong"})
    assert denied.status_code == 401
    assert denied.json()["error"]["code"] == "unauthorized"

    hunted = client.post(f"/api/wants/{want_id}/hunt", headers=headers)
    assert hunted.status_code == 200
    after = hunted.json()
    assert after["status"] in {"hunting", "negotiating", "done"}
    assert after["matches"]
    assert after["matches"][0]["listing_id"] == "lst_02"
    assert after["matches"][0]["appraisal"]["verdict"]
    assert after["matches"][0]["inspection"]["trust_level"]
    assert 0 < after["matches"][0]["score"] <= 1
    assert after["negotiations"]
    assert all(match["price"] <= 400 for match in after["matches"])

    targeted = client.post(
        f"/api/wants/{want_id}/target",
        headers=headers,
        json={"listing_id": "lst_03"},
    )
    assert targeted.status_code == 200
    cargo = next(item for item in targeted.json()["negotiations"] if item["listing_id"] == "lst_03")
    assert cargo["outcome"] == "no_deal"

    home = client.get("/")
    assert home.status_code == 200
