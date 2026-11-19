"""Single Grok seam. Person B owns complete().

Read GROK_API_KEY, GROK_API_BASE_URL, and GROK_MODEL from the environment only.
Never log the key. Never put server-only negotiation bounds in the prompt.
On a missing key, timeout, or error, return None so the caller keeps its stub.
"""

from __future__ import annotations

import base64
import json
import os
import re

import httpx

_DEFAULT_BASE_URL = "https://api.x.ai/v1"
_DEFAULT_MODEL = "grok-4.7"
_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def complete(prompt: str, *, image: bytes | None = None, timeout_s: float = 8.0) -> str | None:
    key = os.environ.get("GROK_API_KEY", "").strip()
    if not key or timeout_s <= 0 or not prompt.strip():
        return None
    base = os.environ.get("GROK_API_BASE_URL", "").strip() or _DEFAULT_BASE_URL
    model = os.environ.get("GROK_MODEL", "").strip() or _DEFAULT_MODEL
    url = base.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "stream": False,
        "messages": [{"role": "user", "content": _message_content(prompt, image)}],
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout_s), follow_redirects=False) as client:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {key}"},
                json=body,
            )
        if response.status_code != 200:
            return None
        return _choice_text(response.json())
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
    return [
        {"type": "text", "text": prompt},
        {
            "type": "image_url",
            "image_url": {"url": _data_url(image), "detail": "high"},
        },
    ]


def _data_url(image: bytes) -> str:
    encoded = base64.b64encode(image).decode("ascii")
    return f"data:{_image_mime(image)};base64,{encoded}"


def _image_mime(image: bytes) -> str:
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image.startswith(b"GIF87a") or image.startswith(b"GIF89a"):
        return "image/gif"
    if len(image) >= 12 and image.startswith(b"RIFF") and image[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _choice_text(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if isinstance(content, str):
        text = content.strip()
        return text or None
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                chunks.append(part["text"])
        text = "".join(chunks).strip()
        return text or None
    return None


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
