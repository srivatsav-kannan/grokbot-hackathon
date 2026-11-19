"""Single Claude seam. Person B owns complete().

Read ANTHROPIC_API_KEY and ANTHROPIC_MODEL from the environment only.
Never log the key. Never put server-only negotiation bounds in the prompt.
On a missing key, timeout, or error, return None so the caller keeps its stub.
"""

from __future__ import annotations

import base64
import json
import os
import re

import httpx

_API_URL = "https://api.anthropic.com/v1/messages"
_API_VERSION = "2023-06-01"
_DEFAULT_MODEL = "claude-sonnet-5-5"
_MAX_TOKENS = 1024
_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def complete(prompt: str, *, image: bytes | None = None, timeout_s: float = 8.0) -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or timeout_s <= 0 or not prompt.strip():
        return None
    model = os.environ.get("ANTHROPIC_MODEL", "").strip() or _DEFAULT_MODEL
    body = {
        "model": model,
        "max_tokens": _MAX_TOKENS,
        "messages": [{"role": "user", "content": _message_content(prompt, image)}],
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout_s), follow_redirects=False) as client:
            response = client.post(
                _API_URL,
                headers={
                    "x-api-key": key,
                    "anthropic-version": _API_VERSION,
                    "content-type": "application/json",
                },
                json=body,
            )
        if response.status_code != 200:
            return None
        return _message_text(response.json())
    except Exception:
        return None


def parse_json_reply(text: str | None) -> dict | list | None:
    """Return the JSON object or array in a model reply, or None."""

    if not text or not text.strip():
        return None
    raw = text.strip()
    candidates = [raw]
    for block in _FENCE.findall(raw):
        stripped = block.strip()
        if stripped:
            candidates.append(stripped)
    balanced_object = _balanced_json(raw, "{")
    balanced_array = _balanced_json(raw, "[")
    if balanced_object:
        candidates.append(balanced_object)
    if balanced_array:
        candidates.append(balanced_array)
    for candidate in candidates:
        parsed = _loads_container(candidate)
        if parsed is not None:
            return parsed
    return None


def _message_content(prompt: str, image: bytes | None) -> str | list[dict[str, object]]:
    if not image:
        return prompt
    encoded = base64.b64encode(image).decode("ascii")
    return [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": _image_mime(image),
                "data": encoded,
            },
        },
        {"type": "text", "text": prompt},
    ]


def _image_mime(image: bytes) -> str:
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image.startswith(b"GIF87a") or image.startswith(b"GIF89a"):
        return "image/gif"
    if len(image) >= 12 and image.startswith(b"RIFF") and image[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _message_text(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    content = payload.get("content")
    if isinstance(content, str):
        text = content.strip()
        return text or None
    if not isinstance(content, list):
        return None
    chunks: list[str] = []
    for part in content:
        if isinstance(part, str):
            chunks.append(part)
        elif isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
            chunks.append(part["text"])
    text = "".join(chunks).strip()
    return text or None


def _loads_container(candidate: str) -> dict | list | None:
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, (dict, list)):
        return parsed
    return None


def _balanced_json(text: str, opener: str) -> str | None:
    closer = "}" if opener == "{" else "]"
    start = text.find(opener)
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None
