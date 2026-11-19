"""Hunt runner. Person C (@heruirayli) owns this file.

Routes call run_hunt(). Today it finishes inline so the demo needs no queue.
Replace the body with a background worker later. Keep the signature.
Do not log want ceilings or access tokens.
"""

from __future__ import annotations


def run_hunt(want_id: str) -> None:
    from backend.app.services import execute_hunt

    execute_hunt(want_id)


def run_target(want_id: str, listing_id: str) -> None:
    from backend.app.services import execute_target

    execute_target(want_id, listing_id)
