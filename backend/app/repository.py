"""SQLite access. Price limit rows are read only by the negotiation service."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from backend.app.db import connect
from backend.app.schemas import (
    Appraisal,
    Comp,
    Inspection,
    Negotiation,
    NegotiationMessage,
    Signal,
)


@dataclass(frozen=True)
class ListingRecord:
    id: str
    category: str
    title: str
    description: str
    price: int
    photos: list[str]
    neighborhood: str
    source_url: str | None
    posted_at: str
    origin: str


@dataclass(frozen=True)
class Limits:
    buyer_max: int
    seller_min: int


def _listing_from_row(row: sqlite3.Row) -> ListingRecord:
    return ListingRecord(
        id=row["id"],
        category=row["category"],
        title=row["title"],
        description=row["description"],
        price=row["price"],
        photos=json.loads(row["photos"]),
        neighborhood=row["neighborhood"],
        source_url=row["source_url"],
        posted_at=row["posted_at"],
        origin=row["origin"],
    )


def count_listings(category: str | None = None) -> int:
    query = "SELECT COUNT(*) AS n FROM listings"
    params: list[str] = []
    if category:
        query += " WHERE category = ?"
        params.append(category)
    with connect() as conn:
        row = conn.execute(query, params).fetchone()
    return int(row["n"])


def list_listings(category: str | None, q: str | None) -> list[ListingRecord]:
    query = "SELECT * FROM listings WHERE 1=1"
    params: list[str] = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if q:
        query += " AND (lower(title) LIKE ? OR lower(description) LIKE ?)"
        like = f"%{q.lower()}%"
        params.extend([like, like])
    query += " ORDER BY posted_at DESC"
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_listing_from_row(row) for row in rows]


def get_listing(listing_id: str) -> ListingRecord | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    if row is None:
        return None
    return _listing_from_row(row)


def get_appraisal(listing_id: str) -> Appraisal | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM appraisals WHERE listing_id = ?", (listing_id,)).fetchone()
    if row is None:
        return None
    comps = [Comp.model_validate(item) for item in json.loads(row["comps"])]
    return Appraisal(
        estimated_value=row["estimated_value"],
        low=row["low"],
        high=row["high"],
        comps=comps,
        verdict=row["verdict"],
    )


def get_inspection(listing_id: str) -> Inspection | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM inspections WHERE listing_id = ?", (listing_id,)).fetchone()
    if row is None:
        return None
    signals = [Signal.model_validate(item) for item in json.loads(row["signals"])]
    return Inspection(trust_level=row["trust_level"], signals=signals)


def insert_listing(
    listing: ListingRecord,
    appraisal: Appraisal,
    inspection: Inspection,
    limits: Limits,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO listings (
                id, category, title, description, price, photos, neighborhood,
                source_url, posted_at, origin
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                listing.id,
                listing.category,
                listing.title,
                listing.description,
                listing.price,
                json.dumps(listing.photos),
                listing.neighborhood,
                listing.source_url,
                listing.posted_at,
                listing.origin,
            ),
        )
        conn.execute(
            """
            INSERT INTO appraisals (listing_id, estimated_value, low, high, comps, verdict)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                listing.id,
                appraisal.estimated_value,
                appraisal.low,
                appraisal.high,
                json.dumps([comp.model_dump() for comp in appraisal.comps]),
                appraisal.verdict,
            ),
        )
        conn.execute(
            """
            INSERT INTO inspections (listing_id, trust_level, signals)
            VALUES (?, ?, ?)
            """,
            (
                listing.id,
                inspection.trust_level,
                json.dumps([signal.model_dump() for signal in inspection.signals]),
            ),
        )
        conn.execute(
            """
            INSERT INTO price_limits (listing_id, want_id, buyer_max, seller_min)
            VALUES (?, NULL, ?, ?)
            """,
            (listing.id, limits.buyer_max, limits.seller_min),
        )


def get_limits(listing_id: str) -> Limits | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT buyer_max, seller_min FROM price_limits
            WHERE listing_id = ? AND want_id IS NULL
            """,
            (listing_id,),
        ).fetchone()
    if row is None or row["buyer_max"] is None or row["seller_min"] is None:
        return None
    return Limits(buyer_max=row["buyer_max"], seller_min=row["seller_min"])


def insert_negotiation(item: Negotiation) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO negotiations (id, listing_id, want_id, status, outcome, messages)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                item.id,
                item.listing_id,
                item.want_id,
                item.status,
                item.outcome,
                json.dumps([message.model_dump(by_alias=True) for message in item.messages]),
            ),
        )


@dataclass(frozen=True)
class WantRecord:
    id: str
    text: str
    category: str | None
    area: str | None
    keywords: list[str]
    status: str
    created_at: str


@dataclass(frozen=True)
class WantMatchRow:
    listing_id: str
    score: float
    reason: str
    negotiation_id: str | None


def insert_want(
    want_id: str,
    text: str,
    category: str | None,
    area: str | None,
    keywords: list[str],
    status: str,
    created_at: str,
    max_price: int | None,
    token_hash: str,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO wants (id, text, category, area, keywords, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (want_id, text, category, area, json.dumps(keywords), status, created_at),
        )
        conn.execute(
            "INSERT INTO want_access (want_id, token_hash) VALUES (?, ?)",
            (want_id, token_hash),
        )
        if max_price is not None:
            conn.execute(
                """
                INSERT INTO price_limits (listing_id, want_id, buyer_max, seller_min)
                VALUES (NULL, ?, ?, NULL)
                """,
                (want_id, max_price),
            )


def get_want(want_id: str) -> WantRecord | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT id, text, category, area, keywords, status, created_at
            FROM wants WHERE id = ?
            """,
            (want_id,),
        ).fetchone()
    if row is None:
        return None
    return WantRecord(
        id=row["id"],
        text=row["text"],
        category=row["category"],
        area=row["area"],
        keywords=json.loads(row["keywords"]),
        status=row["status"],
        created_at=row["created_at"],
    )


def get_token_hash(want_id: str) -> str | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT token_hash FROM want_access WHERE want_id = ?",
            (want_id,),
        ).fetchone()
    if row is None:
        return None
    return str(row["token_hash"])


def get_want_max(want_id: str) -> int | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT buyer_max FROM price_limits
            WHERE want_id = ? AND listing_id IS NULL
            """,
            (want_id,),
        ).fetchone()
    if row is None or row["buyer_max"] is None:
        return None
    return int(row["buyer_max"])


def set_want_status(want_id: str, status: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE wants SET status = ? WHERE id = ?", (status, want_id))


def upsert_want_match(
    want_id: str,
    listing_id: str,
    score: float,
    reason: str,
    negotiation_id: str | None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO want_matches (want_id, listing_id, score, reason, negotiation_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(want_id, listing_id) DO UPDATE SET
                score = excluded.score,
                reason = excluded.reason,
                negotiation_id = COALESCE(excluded.negotiation_id, want_matches.negotiation_id)
            """,
            (want_id, listing_id, score, reason, negotiation_id),
        )


def list_want_matches(want_id: str) -> list[WantMatchRow]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT listing_id, score, reason, negotiation_id
            FROM want_matches
            WHERE want_id = ?
            ORDER BY score DESC, listing_id ASC
            """,
            (want_id,),
        ).fetchall()
    return [
        WantMatchRow(
            listing_id=row["listing_id"],
            score=float(row["score"]),
            reason=row["reason"],
            negotiation_id=row["negotiation_id"],
        )
        for row in rows
    ]


def list_negotiations_for_want(want_id: str) -> list[Negotiation]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id FROM negotiations WHERE want_id = ? ORDER BY id ASC",
            (want_id,),
        ).fetchall()
    found: list[Negotiation] = []
    for row in rows:
        item = get_negotiation(row["id"])
        if item is not None:
            found.append(item)
    return found


def get_negotiation(negotiation_id: str) -> Negotiation | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM negotiations WHERE id = ?",
            (negotiation_id,),
        ).fetchone()
    if row is None:
        return None
    messages = [NegotiationMessage.model_validate(item) for item in json.loads(row["messages"])]
    return Negotiation(
        id=row["id"],
        listing_id=row["listing_id"],
        want_id=row["want_id"],
        status=row["status"],
        outcome=row["outcome"],
        messages=messages,
    )
