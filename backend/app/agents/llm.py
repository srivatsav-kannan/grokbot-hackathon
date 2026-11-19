"""Single Grok seam. Person B replaces the body of complete().

Read GROK_API_KEY and GROK_API_BASE_URL from the environment only.
Never log the key. Never put server-only negotiation bounds in the prompt.
On a missing key, timeout, or error, return None so the caller keeps its stub.
"""

from __future__ import annotations

import os


def complete(prompt: str, *, image: bytes | None = None, timeout_s: float = 8.0) -> str | None:
    key = os.environ.get("GROK_API_KEY", "").strip()
    if not key:
        return None
    _ = (prompt, image, timeout_s, os.environ.get("GROK_API_BASE_URL", "").strip())
    # Stub: a real HTTP call belongs here. Returning None forces the stub result.
    return None
