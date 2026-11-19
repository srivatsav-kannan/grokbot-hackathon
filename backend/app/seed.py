"""Seed listings labeled origin=seed. Placeholder art, no real people.

Private ceilings for the on-site negotiate path live only in `_LIMITS` and the
price_limits table. Do not print them, return them, or copy them into docs or
the frontend.

Person C (@heruirayli) owns this file.
"""

from __future__ import annotations

from backend.app.agents.appraiser import appraise
from backend.app.agents.inspector import inspect
from backend.app.repository import Limits, ListingRecord, insert_listing

# Server-only. Not part of any response model.
_LIMITS: dict[str, tuple[int, int]] = {
    "lst_01": (307, 241),
    "lst_02": (419, 301),
    "lst_03": (199, 510),
    "lst_04": (251, 151),
    "lst_05": (503, 381),
    "lst_06": (761, 641),
    "lst_07": (299, 801),
    "lst_08": (701, 501),
    "lst_09": (127, 71),
    "lst_10": (263, 181),
    "lst_11": (211, 401),
    "lst_12": (233, 157),
}

_ROWS: tuple[dict[str, object], ...] = (
    {
        "id": "lst_01",
        "category": "bikes",
        "title": "City bike, ready to ride",
        "description": "Commuter frame with a recent tune-up and lights already fitted.",
        "price": 280,
        "photos": ["/placeholders/bike.svg"],
        "neighborhood": "Temescal, Oakland",
        "posted_at": "2026-11-19T15:00:00Z",
    },
    {
        "id": "lst_02",
        "category": "bikes",
        "title": "Aluminum road bike",
        "description": "Drop bars, two water-bottle mounts, tires with plenty of tread left.",
        "price": 360,
        "photos": ["/placeholders/bike.svg"],
        "neighborhood": "Mission, San Francisco",
        "posted_at": "2026-11-19T18:30:00Z",
    },
    {
        "id": "lst_03",
        "category": "bikes",
        "title": "Cargo bike with wooden box",
        "description": "Long-tail cargo bike. The wooden box latches. Heavy to carry upstairs.",
        "price": 620,
        "photos": ["/placeholders/bike.svg"],
        "neighborhood": "Bernal Heights, San Francisco",
        "posted_at": "2026-11-19T12:00:00Z",
    },
    {
        "id": "lst_04",
        "category": "bikes",
        "title": "Folding commuter bike",
        "description": "Folds for a train ride. Small scuffs on the hinge, gears shift cleanly.",
        "price": 190,
        "photos": ["/placeholders/bike.svg"],
        "neighborhood": "Downtown Berkeley",
        "posted_at": "2026-11-18T20:00:00Z",
    },
    {
        "id": "lst_05",
        "category": "computers",
        "title": "Refurbished 14-inch laptop",
        "description": "Refurbished laptop with a new battery and a charger in the box.",
        "price": 450,
        "photos": ["/placeholders/computer.svg"],
        "neighborhood": "SoMa, San Francisco",
        "posted_at": "2026-11-19T17:10:00Z",
    },
    {
        "id": "lst_06",
        "category": "computers",
        "title": "Desktop tower for classwork",
        "description": "Quiet tower with room for a second drive. Monitor is not included.",
        "price": 700,
        "photos": ["/placeholders/computer.svg"],
        "neighborhood": "Palo Alto",
        "posted_at": "2026-11-19T11:00:00Z",
    },
    {
        "id": "lst_07",
        "category": "computers",
        "title": "27-inch monitor and stand",
        "description": "Wide monitor on a metal stand. A display cable is included.",
        "price": 1100,
        "photos": ["/placeholders/computer.svg"],
        "neighborhood": "Downtown Oakland",
        "posted_at": "2026-11-17T16:00:00Z",
    },
    {
        "id": "lst_08",
        "category": "computers",
        "title": "Small form-factor PC",
        "description": "Compact desktop that sits on a bookshelf. Includes a power cord.",
        "price": 640,
        "photos": ["/placeholders/computer.svg"],
        "neighborhood": "Sunnyvale",
        "posted_at": "2026-11-19T09:40:00Z",
    },
    {
        "id": "lst_09",
        "category": "furniture",
        "title": "Solid wood desk",
        "description": "Small writing desk. One edge is worn. The drawers open and close.",
        "price": 80,
        "photos": ["/placeholders/furniture.svg"],
        "neighborhood": "Mission, San Francisco",
        "posted_at": "2026-11-19T19:00:00Z",
    },
    {
        "id": "lst_10",
        "category": "furniture",
        "title": "Two-seat sofa",
        "description": "Two-seat sofa in a light fabric. No tears. Pickup from a ground-floor room.",
        "price": 240,
        "photos": ["/placeholders/furniture.svg"],
        "neighborhood": "Hayes Valley, San Francisco",
        "posted_at": "2026-11-19T13:20:00Z",
    },
    {
        "id": "lst_11",
        "category": "furniture",
        "title": "Dining table with four chairs",
        "description": "Rectangular table and four matching chairs. A few marks on the top.",
        "price": 450,
        "photos": ["/placeholders/furniture.svg"],
        "neighborhood": "Berkeley",
        "posted_at": "2026-11-16T18:00:00Z",
    },
    {
        "id": "lst_12",
        "category": "furniture",
        "title": "Tall bookshelf",
        "description": "Tall shelf.",
        "price": 200,
        "photos": ["/placeholders/furniture.svg"],
        "neighborhood": "Richmond District, San Francisco",
        "posted_at": "2026-11-19T08:15:00Z",
    },
)


def load_seed() -> None:
    for row in _ROWS:
        listing = ListingRecord(
            id=str(row["id"]),
            category=str(row["category"]),
            title=str(row["title"]),
            description=str(row["description"]),
            price=int(row["price"]),  # type: ignore[arg-type]
            photos=list(row["photos"]),  # type: ignore[arg-type]
            neighborhood=str(row["neighborhood"]),
            source_url=None,
            posted_at=str(row["posted_at"]),
            origin="seed",
        )
        buyer_max, seller_min = _LIMITS[listing.id]
        appraisal = appraise(listing)
        insert_listing(
            listing,
            appraisal,
            inspect(listing, appraisal),
            Limits(buyer_max=buyer_max, seller_min=seller_min),
        )
