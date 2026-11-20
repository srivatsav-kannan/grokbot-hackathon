"""Hunt runner. Person C (@heruirayli) owns this file.

Routes call run_hunt(). Hunts run in a background thread, one at a time per buyer bot.
Do not log want ceilings or access tokens.
"""

from __future__ import annotations

import logging
import threading


_RUNNING: set[str] = set()
_LOCK = threading.Lock()


def run_hunt(want_id: str) -> None:
    """Hunts negotiate with several listings, which takes longer than one web request.
    Run each in the background, one at a time per buyer bot. The Deals page polls."""

    import os

    from backend.app.services import execute_hunt

    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("FAIRLOT_SYNC_HUNT") == "1":
        execute_hunt(want_id)
        return
    with _LOCK:
        if want_id in _RUNNING:
            return
        _RUNNING.add(want_id)

    def work() -> None:
        try:
            execute_hunt(want_id)
        except Exception:  # noqa: BLE001
            logging.getLogger(__name__).exception("hunt failed for %s", want_id)
        finally:
            with _LOCK:
                _RUNNING.discard(want_id)

    threading.Thread(target=work, name=f"hunt-{want_id}", daemon=True).start()


def run_target(want_id: str, listing_id: str) -> None:
    from backend.app.services import execute_target

    execute_target(want_id, listing_id)
