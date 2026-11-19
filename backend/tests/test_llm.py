"""complete() stays offline without a key and never records that key."""

from __future__ import annotations

import json

import httpx
import pytest

from backend.app.agents.llm import complete, parse_json_reply


def test_complete_returns_none_without_a_key(monkeypatch):
    monkeypatch.delenv("GROK_API_KEY", raising=False)

    def explode(*_args, **_kwargs):
        raise AssertionError("HTTP client should not be constructed without a key")

    monkeypatch.setattr(httpx, "Client", explode)
    assert complete("Price this bike.") is None
    assert complete("   ", image=b"\xff\xd8\xff") is None
    assert complete("Price this bike.", timeout_s=0) is None


def test_complete_returns_none_on_timeout_and_http_error(monkeypatch):
    monkeypatch.setenv("GROK_API_KEY", "test-key-not-real")
    monkeypatch.delenv("GROK_API_BASE_URL", raising=False)
    monkeypatch.delenv("GROK_MODEL", raising=False)

    class TimeoutClient:
        def __init__(self, *args, **kwargs):
            self.timeout = kwargs.get("timeout")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, *_args, **_kwargs):
            raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "Client", TimeoutClient)
    assert complete("hello") is None

    class ErrorClient(TimeoutClient):
        def post(self, *_args, **_kwargs):
            raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "Client", ErrorClient)
    assert complete("hello") is None


def test_complete_posts_chat_completions_and_image_data_url(monkeypatch):
    monkeypatch.setenv("GROK_API_KEY", "test-key-not-real")
    monkeypatch.setenv("GROK_API_BASE_URL", "https://api.x.ai/v1/")
    monkeypatch.setenv("GROK_MODEL", "grok-test")
    captured: dict = {}

    class OkResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "  {\"ok\": true}  "}}]}

    class OkClient:
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            captured["follow_redirects"] = kwargs.get("follow_redirects")

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, url, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return OkResponse()

    monkeypatch.setattr(httpx, "Client", OkClient)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    assert complete("Describe the photo.", image=png, timeout_s=3.5) == '{"ok": true}'
    assert captured["url"] == "https://api.x.ai/v1/chat/completions"
    assert captured["json"]["model"] == "grok-test"
    assert captured["headers"]["Authorization"] == "Bearer test-key-not-real"
    assert captured["follow_redirects"] is False
    content = captured["json"]["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "Describe the photo."}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "test-key-not-real" not in json.dumps(captured["json"])


def test_complete_reads_text_parts_and_rejects_non_200(monkeypatch):
    monkeypatch.setenv("GROK_API_KEY", "test-key-not-real")

    class PartsResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": [{"type": "text", "text": "hi"}]}}]}

    class BadResponse:
        status_code = 500

        def json(self):
            return {}

    calls = {"n": 0}

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, *_args, **_kwargs):
            calls["n"] += 1
            return PartsResponse() if calls["n"] == 1 else BadResponse()

    monkeypatch.setattr(httpx, "Client", Client)
    assert complete("hello") == "hi"
    assert complete("hello") is None


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ('{"category": "bikes"}', {"category": "bikes"}),
        ('```json\n{"low": 10}\n```', {"low": 10}),
        ('Sure. {"signals": []} thanks', {"signals": []}),
        ("[1, 2]", [1, 2]),
        ("not json", None),
        ("", None),
        (None, None),
        ("42", None),
    ],
)
def test_parse_json_reply(reply, expected):
    assert parse_json_reply(reply) == expected
