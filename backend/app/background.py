"""Always-on agent loop. Failures are logged and the next tick still runs."""

from __future__ import annotations

import asyncio
import logging
import os

log = logging.getLogger("fairlot.background")


def interval_seconds() -> int:
    raw = os.environ.get("BACKGROUND_INTERVAL_S", "120").strip() or "120"
    try:
        seconds = int(raw)
    except ValueError:
        seconds = 120
    return max(15, seconds)


def background_enabled() -> bool:
    if os.environ.get("FAIRLOT_BACKGROUND", "1").strip() == "0":
        return False
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return True


async def background_loop(stop: asyncio.Event) -> None:
    wait = interval_seconds()
    while not stop.is_set():
        try:
            await asyncio.to_thread(_tick)
        except Exception:
            log.exception("background tick failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=wait)
            return
        except asyncio.TimeoutError:
            pass


def _tick() -> None:
    from backend.app.services import run_background_tick

    run_background_tick()
