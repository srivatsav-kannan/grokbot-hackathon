"""Offline Scout coverage. Fixtures stand in for public pages. No network."""

from __future__ import annotations

import hashlib
import inspect
import time
from pathlib import Path

import httpx
import pytest

from backend.app.agents import scout
from backend.app.repository import ListingRecord
from backend.app.sources.craigslist import parse_search_page
from backend.app.sources.ebay import parse_finding_json, parse_search_html
from backend.app.sources.listing import dedupe
from backend.app.sources.mercari import parse_search_page as parse_mercari
from backend.app.sources.offerup import parse_search_page as parse_offerup
from backend.app.sources.places import location_is_bay, location_is_outside

FIXTURES = Path(__file__).parent / "fixtures"


def _text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _response(url: str, status: int, body: str) -> httpx.Response:
    return httpx.Response(
        status,
        headers={"content-type": "text/html; charset=utf-8"},
        text=body,
        request=httpx.Request("GET", url),
    )


def _route(url: str) -> httpx.Response:
    if "craigslist.org" in url:
        return _response(url, 200, _text("craigslist_bikes.html"))
    if "offerup.com" in url:
        return _response(url, 200, _text("offerup_bikes.html"))
    if "svcs.ebay.com" in url:
        return _response(url, 200, _text("ebay_finding.json"))
    if "ebay.com" in url:
        return _response(url, 200, _text("ebay_bikes.html"))
    if "mercari.com" in url:
        return _response(url, 200, _text("mercari_bikes.html"))
    raise AssertionError(f"unexpected fetch {url}")


@pytest.fixture()
def offline(monkeypatch, tmp_path):
    calls: list[str] = []

    def fake_get(url: str) -> httpx.Response:
        calls.append(url)
        return _route(url)

    monkeypatch.setenv("SCOUT_LIVE", "1")
    monkeypatch.setenv("SCOUT_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("EBAY_APP_ID", raising=False)
    monkeypatch.setattr(scout, "_http_get", fake_get)
    monkeypatch.setattr(scout, "_sleep", lambda _seconds: None)
    return calls


def test_live_off_does_not_fetch(monkeypatch):
    monkeypatch.delenv("SCOUT_LIVE", raising=False)

    def explode(_url: str):
        raise AssertionError("network")

    monkeypatch.setattr(scout, "_http_get", explode)
    result = scout.scout_run(["bikes", "computers", "furniture"])
    assert result.listings == []
    assert result.stopped is False
    assert result.report is None
    assert result.sources == []


def test_craigslist_parser_scrubs_and_keeps_photo():
    items = parse_search_page(_text("craigslist_bikes.html"))
    assert [item.title for item in items] == ["City bike", "Laptop", "City bike duplicate post"]
    assert items[0].price == 320
    assert items[0].neighborhood == "Mission District"
    assert items[0].image == "https://images.craigslist.org/bike.jpg"
    assert items[0].images[1] == "https://images.craigslist.org/bike-2.jpg"
    assert "seller@example.com" not in items[1].title


def test_ebay_html_parses_items_and_scrubs_a_phone_number():
    rows = parse_search_html(_text("ebay_bikes.html"))
    assert [row["external_id"] for row in rows] == ["222222222222", "333333333333", "444444444444"]
    assert rows[2]["title"] == "Call about this bike"
    assert "415" not in str(rows[2]["title"])


def test_ebay_finding_json_reads_price_and_time():
    rows = parse_finding_json(_text("ebay_finding.json"))
    assert rows[0]["price"] == 640
    assert rows[0]["posted_at"] == "2026-11-01T15:04:00.000Z"
    assert rows[1]["location"] == "Austin, TX"


def test_offerup_and_mercari_parsers_see_locations():
    offerup = parse_offerup(_text("offerup_bikes.html"))
    assert [row["location"] for row in offerup] == [
        "Mission, San Francisco, CA",
        "Wichita, KS",
        "Oakland, CA",
    ]
    mercari = parse_mercari(_text("mercari_bikes.html"))
    assert [row["external_id"] for row in mercari] == ["m100", "m200", "m300"]
    assert mercari[0]["posted_at"] == "2026-11-01T15:00:00Z"


def test_craigslist_drops_a_named_place_outside_the_bay():
    from backend.app.sources.craigslist import listings_from_page

    body = """
    <li class="cl-static-search-result">
    <a href="https://www.craigslist.org/view/d/tandem/OutSideBayId0000000001">
    <div class="title">Tandem</div>
    <div class="price">$500</div>
    <div class="location">Corona, California, United States</div>
    </a></li>
    <li class="cl-static-search-result">
    <a href="https://www.craigslist.org/view/d/tandem/InSideBayId00000000002">
    <div class="title">Tandem</div>
    <div class="price">$400</div>
    <div class="location">berkeley</div>
    </a></li>
    """
    found = listings_from_page(body, "bikes", "2026-11-19T00:00:00Z")
    assert [item.neighborhood for item in found] == ["Berkeley"]


def test_place_filter():
    assert location_is_bay("Mission, San Francisco, CA")
    assert location_is_bay("Oakland, CA")
    assert not location_is_bay("Wichita, KS")
    assert not location_is_bay("Fairfax, VA")
    assert location_is_outside("Los Angeles, CA")
    assert location_is_outside("Austin, TX")
    assert not location_is_outside("mission district")
    assert not location_is_outside("")


def test_dedupe_is_per_source_and_external_id():
    posted = "2026-11-19T00:00:00Z"
    common = dict(
        category="bikes",
        title="Bike",
        price=10,
        neighborhood="Oakland, CA",
        photos=["https://images.example/bike.jpg"],
        posted_at=posted,
    )
    from backend.app.sources.listing import build_listing

    first = build_listing(source="offerup", external_id="same", source_url="https://offerup.com/item/detail/same", **common)
    second = build_listing(source="ebay", external_id="same", source_url="https://www.ebay.com/itm/123456789012", **common)
    third = build_listing(source="offerup", external_id="same", source_url="https://offerup.com/item/detail/same", **common)
    assert first is not None and second is not None and third is not None
    kept = dedupe([first, second, third])
    assert [(item.source, item.external_id) for item in kept] == [("offerup", "same"), ("ebay", "same")]


def test_scout_run_normalizes_and_skips_login_sources(offline):
    result = scout.scout_run(["bikes"])
    by_source: dict[str, list] = {}
    for listing in result.listings:
        assert isinstance(listing, ListingRecord)
        assert listing.source_url
        assert listing.origin == "scout"
        assert listing.source
        assert listing.external_id
        by_source.setdefault(listing.source, []).append(listing)

    assert set(by_source) == {"craigslist", "ebay", "offerup", "mercari"}
    assert by_source["craigslist"][0].title == "City bike"
    assert by_source["craigslist"][0].external_id == "1234567890"
    assert by_source["craigslist"][0].photos[0] == "https://images.craigslist.org/bike.jpg"
    assert by_source["ebay"][0].neighborhood == "San Francisco, CA"
    assert all("Los Angeles" not in item.neighborhood for item in by_source["ebay"])
    assert by_source["offerup"][0].neighborhood == "Mission, San Francisco, CA"
    assert by_source["offerup"][0].source_url.startswith("https://offerup.com/item/detail/")
    assert by_source["mercari"][0].posted_at == "2026-11-01T15:00:00Z"
    assert "user@" not in by_source["mercari"][0].title

    craigslist_id = "lst_cl_" + hashlib.sha256(
        "https://sfbay.craigslist.org/sfc/bik/d/city-bike/1234567890.html".encode()
    ).hexdigest()[:12]
    assert by_source["craigslist"][0].id == craigslist_id
    assert len({item.id for item in result.listings}) == len(result.listings)

    reports = {item.source: item for item in result.sources}
    assert reports["facebook"].skipped is True
    assert reports["nextdoor"].skipped is True
    assert reports["facebook"].fetched == 0
    assert "sign-in" in reports["facebook"].message
    assert result.stopped is False
    assert not any("facebook.com" in url or "nextdoor.com" in url for url in offline)


def test_block_stops_only_that_source(offline, monkeypatch):
    def fake_get(url: str) -> httpx.Response:
        if "ebay.com" in url:
            return _response(url, 403, "blocked")
        if "mercari.com" in url:
            return _response(url, 200, '<html><div class="captcha-container">verify</div></html>')
        return _route(url)

    monkeypatch.setattr(scout, "_http_get", fake_get)
    result = scout.scout_run(["bikes"])
    assert {listing.source for listing in result.listings} == {"craigslist", "offerup"}
    assert result.stopped is True
    assert result.report is not None
    assert result.report.reason == "captcha"
    reports = {item.source: item for item in result.sources}
    assert reports["ebay"].stopped is True
    assert reports["ebay"].reason == "blocked"
    assert reports["mercari"].reason == "captcha"
    assert reports["craigslist"].stopped is False


def test_block_before_any_listing_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("SCOUT_LIVE", "1")
    monkeypatch.setenv("SCOUT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(scout, "_sleep", lambda _seconds: None)

    def fake_get(url: str) -> httpx.Response:
        return _response(url, 429, "slow down")

    monkeypatch.setattr(scout, "_http_get", fake_get)
    with pytest.raises(scout.ScoutStopped) as caught:
        scout.scout_run(["bikes"])
    assert caught.value.reason == "blocked"
    assert "will not retry" in caught.value.message


def test_page_budget_is_per_source(offline, monkeypatch):
    monkeypatch.setattr(scout, "MAX_PAGES_PER_RUN", 1)
    scout.scout_run(["bikes", "computers", "furniture"])
    hosts = {"craigslist": 0, "offerup": 0, "ebay": 0, "mercari": 0}
    for url in offline:
        for name in hosts:
            if name in url:
                hosts[name] += 1
    assert hosts == {"craigslist": 1, "offerup": 1, "ebay": 1, "mercari": 1}


def test_cache_skips_a_second_fetch(offline):
    first = scout.scout_run(["bikes"])
    assert offline
    used = len(offline)
    second = scout.scout_run(["bikes"])
    assert offline[used:] == []
    assert [item.id for item in second.listings] == [item.id for item in first.listings]


def test_ebay_app_id_uses_finding_api_not_the_search_page(offline, monkeypatch):
    monkeypatch.setenv("EBAY_APP_ID", "test-app-id")
    result = scout.scout_run(["computers"])
    ebay_urls = [url for url in offline if "ebay" in url]
    assert ebay_urls
    assert all("svcs.ebay.com" in url for url in ebay_urls)
    assert all("SECURITY-APPNAME=test-app-id" in url for url in ebay_urls)
    assert all("www.ebay.com/sch" not in url for url in ebay_urls)
    ebay_listings = [item for item in result.listings if item.source == "ebay"]
    assert len(ebay_listings) == 1
    assert ebay_listings[0].title == "Laptop from a neighbor"
    assert ebay_listings[0].posted_at == "2026-11-01T15:04:00.000Z"
    assert ebay_listings[0].source_url == "https://www.ebay.com/itm/555555555555"


def test_service_stores_scouted_listings(client, monkeypatch, tmp_path):
    monkeypatch.setenv("SCOUT_LIVE", "1")
    monkeypatch.setenv("SCOUT_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("EBAY_APP_ID", raising=False)
    monkeypatch.setattr(scout, "_http_get", _route)
    monkeypatch.setattr(scout, "_sleep", lambda _seconds: None)

    response = client.post("/api/scout/run", json={"categories": ["bikes"]})
    assert response.status_code == 200
    body = response.json()
    assert body["added"] >= 1
    assert "buyer_max" not in response.text
    assert "seller_min" not in response.text

    listed = client.get("/api/listings", params={"q": "City bike"})
    assert listed.status_code == 200
    cards = [row for row in listed.json()["listings"] if row["origin"] == "scout"]
    assert cards
    detail = client.get(f"/api/listings/{cards[0]['id']}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["origin"] == "scout"
    assert payload["source_url"].startswith("https://")
    assert payload["neighborhood"]


def test_craigslist_view_url_uses_the_public_id():
    from backend.app.sources.craigslist import listings_from_page

    body = """
    <li class="cl-static-search-result">
    <a href="https://www.craigslist.org/view/d/city-bike/AbCd1234567890xyzXYZ12">
    <div class="title">City bike</div>
    <div class="price">$100</div>
    <div class="location">oakland</div>
    </a></li>
    """
    found = listings_from_page(body, "bikes", "2026-11-19T00:00:00Z")
    assert len(found) == 1
    assert found[0].external_id == "AbCd1234567890xyzXYZ12"
    assert found[0].source == "craigslist"
    assert found[0].source_url.startswith("https://www.craigslist.org/view/")


def test_scout_query_signature_and_live_off(monkeypatch):
    params = inspect.signature(scout.scout_query).parameters
    assert list(params) == ["query", "category"]
    assert params["category"].default is None
    monkeypatch.delenv("SCOUT_LIVE", raising=False)

    def explode(_url: str, _timeout: float):
        raise AssertionError("network")

    monkeypatch.setattr(scout, "_http_get_timeout", explode)
    assert scout.scout_query("road bike") == []
    assert scout.scout_query("   ") == []
    assert scout.scout_query("bike", category="cars") == []


def test_scout_query_searches_each_enabled_source_once(offline, monkeypatch):
    def fake(url: str, _timeout: float) -> httpx.Response:
        offline.append(url)
        return _route(url)

    monkeypatch.setattr(scout, "_http_get_timeout", fake)
    listings = scout.scout_query("tandem", category="bikes")
    assert listings
    assert {item.category for item in listings} == {"bikes"}
    assert {item.source for item in listings} >= {"craigslist", "ebay", "offerup"}
    hosts = {"craigslist": 0, "offerup": 0, "ebay": 0, "mercari": 0}
    for url in offline:
        assert "tandem" in url
        for name in hosts:
            if name in url:
                hosts[name] += 1
    assert hosts == {"craigslist": 1, "offerup": 1, "ebay": 1, "mercari": 1}
    craigslist = next(url for url in offline if "craigslist.org" in url)
    assert "cat=bia" in craigslist
    assert "query=tandem" in craigslist
    assert not any("facebook.com" in url or "nextdoor.com" in url for url in offline)
    assert all(item.source_url.startswith("https://") and item.external_id for item in listings)


def test_scout_query_classifies_when_the_text_names_no_category(offline, monkeypatch):
    def fake(url: str, _timeout: float) -> httpx.Response:
        offline.append(url)
        return _route(url)

    monkeypatch.setattr(scout, "_http_get_timeout", fake)
    listings = scout.scout_query("zzzz")
    assert {item.category for item in listings} == {"bikes", "computers"}
    craigslist = next(url for url in offline if "craigslist.org" in url)
    assert "cat=" not in craigslist
    assert "query=zzzz" in craigslist


def test_scout_query_keeps_other_sources_when_one_is_blocked(offline, monkeypatch):
    def fake(url: str, _timeout: float) -> httpx.Response:
        offline.append(url)
        if "ebay.com" in url:
            return _response(url, 403, "blocked")
        if "mercari.com" in url:
            return _response(url, 200, '<html><div class="captcha-container">verify</div></html>')
        return _route(url)

    monkeypatch.setattr(scout, "_http_get_timeout", fake)
    listings = scout.scout_query("city bike", category="bikes")
    assert listings
    assert {item.source for item in listings} == {"craigslist", "offerup"}
    assert all(item.source != "ebay" for item in listings)


def test_scout_query_returns_within_the_deadline(monkeypatch, tmp_path):
    monkeypatch.setenv("SCOUT_LIVE", "1")
    monkeypatch.setenv("SCOUT_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(scout, "QUERY_DEADLINE_SECONDS", 0.4)
    monkeypatch.setattr(scout, "QUERY_SOURCE_TIMEOUT_SECONDS", 0.2)

    def fake(url: str, _timeout: float) -> httpx.Response:
        if "ebay" in url:
            time.sleep(2.0)
            return _response(url, 200, _text("ebay_bikes.html"))
        return _route(url)

    monkeypatch.setattr(scout, "_http_get_timeout", fake)
    started = time.monotonic()
    listings = scout.scout_query("city bike", category="bikes")
    elapsed = time.monotonic() - started
    assert elapsed < 1.5
    assert listings
    assert all(item.source != "ebay" for item in listings)


def test_scout_query_uses_the_finding_api_when_configured(offline, monkeypatch):
    monkeypatch.setenv("EBAY_APP_ID", "test-app-id")

    def fake(url: str, _timeout: float) -> httpx.Response:
        offline.append(url)
        return _route(url)

    monkeypatch.setattr(scout, "_http_get_timeout", fake)
    listings = scout.scout_query("laptop")
    ebay_urls = [url for url in offline if "ebay" in url]
    assert len(ebay_urls) == 1
    assert "svcs.ebay.com" in ebay_urls[0]
    assert "SECURITY-APPNAME=test-app-id" in ebay_urls[0]
    assert "laptop" in ebay_urls[0]
    ebay_listings = [item for item in listings if item.source == "ebay"]
    assert len(ebay_listings) == 1
    assert ebay_listings[0].category == "computers"
    assert ebay_listings[0].source_url == "https://www.ebay.com/itm/555555555555"
