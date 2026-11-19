"""complete() stays offline without a key and never records that key."""

from __future__ import annotations

import json

import httpx
import pytest

from backend.app.agents.llm import complete, parse_json_reply


def test_complete_returns_none_without_a_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("GROK_API_KEY", "unused-grok-key")

    def explode(*_args, **_kwargs):
        raise AssertionError("HTTP client should not be constructed without a key")

    monkeypatch.setattr(httpx, "Client", explode)
    assert complete("Price this bike.") is None
    assert complete("   ", image=b"\xff\xd8\xff") is None
    assert complete("Price this bike.", timeout_s=0) is None


def test_complete_returns_none_on_timeout_and_http_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

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


def test_complete_posts_messages_and_image_block(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test")
    captured: dict = {}

    class OkResponse:
        status_code = 200

        def json(self):
            return {"content": [{"type": "text", "text": '  {"ok": true}  '}]}

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
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    assert captured["json"]["model"] == "claude-test"
    assert captured["json"]["max_tokens"] == 1024
    assert captured["headers"]["x-api-key"] == "test-key-not-real"
    assert captured["headers"]["anthropic-version"] == "2023-06-01"
    assert captured["follow_redirects"] is False
    content = captured["json"]["messages"][0]["content"]
    assert content[1] == {"type": "text", "text": "Describe the photo."}
    image = content[0]
    assert image["type"] == "image"
    assert image["source"]["type"] == "base64"
    assert image["source"]["media_type"] == "image/png"
    assert image["source"]["data"]
    assert not str(image["source"]["data"]).startswith("data:")
    assert "test-key-not-real" not in json.dumps(captured["json"])


def test_complete_uses_default_sonnet_and_ignores_non_200(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    captured: dict = {}

    class PartsResponse:
        status_code = 200

        def json(self):
            return {
                "content": [
                    {"type": "thinking", "thinking": "hidden"},
                    {"type": "text", "text": "hi"},
                ]
            }

    class BadResponse:
        status_code = 500

        def json(self):
            return {"error": {"message": "nope"}}

    calls = {"n": 0}

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, url, headers, json):
            calls["n"] += 1
            captured["model"] = json["model"]
            captured["url"] = url
            return PartsResponse() if calls["n"] == 1 else BadResponse()

    monkeypatch.setattr(httpx, "Client", Client)
    assert complete("hello") == "hi"
    assert captured["model"] == "claude-sonnet-5-5"
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
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
