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


def list_listings(category: str | None, q: str | None, kind: str | None = None) -> list[ListingRecord]:
    query = "SELECT * FROM listings WHERE 1=1"
    params: list[str] = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if q:
        query += " AND (lower(title) LIKE ? OR lower(description) LIKE ?)"
        like = f"%{q.lower()}%"
        params.extend([like, like])
    if kind == "native":
        query += " AND origin = 'lister'"
    elif kind == "external":
        query += " AND origin = 'scout'"
    elif kind == "sample":
        query += " AND origin = 'seed'"
    else:
        # Demo rows stay in the database for tests. The public feed drops them
        # once a real listing (native or scouted) is stored.
        query += (
            " AND (origin != 'seed' OR NOT EXISTS ("
            "SELECT 1 FROM listings AS live WHERE live.origin != 'seed'))"
        )
    query += (
        " ORDER BY CASE origin WHEN 'lister' THEN 0 WHEN 'seed' THEN 1 ELSE 2 END,"
        " posted_at DESC"
    )
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
    user_id: str | None = None,
) -> None:
    with connect() as conn:
        existing = conn.execute(
            "SELECT 1 FROM listings WHERE id = ?",
            (listing.id,),
        ).fetchone()
        if existing is not None:
            return
        conn.execute(
            """
            INSERT INTO listings (
                id, category, title, description, price, photos, neighborhood,
                source_url, posted_at, origin, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                user_id,
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


def insert_negotiation(item: Negotiation, user_id: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO negotiations (
                id, listing_id, want_id, status, outcome, messages, accepted, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.id,
                item.listing_id,
                item.want_id,
                item.status,
                item.outcome,
                json.dumps([message.model_dump(by_alias=True) for message in item.messages]),
                1 if item.accepted else 0,
                user_id,
            ),
        )


def negotiation_user_id(negotiation_id: str) -> str | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT user_id FROM negotiations WHERE id = ?",
            (negotiation_id,),
        ).fetchone()
    if row is None or row["user_id"] is None:
        return None
    return str(row["user_id"])


def set_negotiation_accepted(negotiation_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE negotiations SET accepted = 1 WHERE id = ?",
            (negotiation_id,),
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
    user_id: str | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO wants (
                id, text, category, area, keywords, status, created_at, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                want_id,
                text,
                category,
                area,
                json.dumps(keywords),
                status,
                created_at,
                user_id,
            ),
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
            SELECT m.listing_id, m.score, m.reason, m.negotiation_id
            FROM want_matches m
            JOIN listings l ON l.id = m.listing_id
            WHERE m.want_id = ?
            ORDER BY CASE l.origin WHEN 'lister' THEN 0 WHEN 'seed' THEN 1 ELSE 2 END,
                     m.score DESC, m.listing_id ASC
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
        accepted=bool(row["accepted"]) if "accepted" in row.keys() else False,
    )


@dataclass(frozen=True)
class UserRecord:
    id: str
    email: str


@dataclass(frozen=True)
class RecommendationRow:
    listing_id: str
    suggested_offer: int
    message: str


def insert_user(user_id: str, email: str, password_hash: str, created_at: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO users (id, email, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, email, password_hash, created_at),
        )


def get_user_by_email(email: str) -> tuple[UserRecord, str] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    if row is None:
        return None
    return UserRecord(id=row["id"], email=row["email"]), str(row["password_hash"])


def get_user(user_id: str) -> UserRecord | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, email FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return UserRecord(id=row["id"], email=row["email"])


def insert_session(token_hash: str, user_id: str, created_at: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, created_at) VALUES (?, ?, ?)",
            (token_hash, user_id, created_at),
        )


def delete_session(token_hash: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def user_for_session(token_hash: str) -> UserRecord | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT users.id, users.email
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
    if row is None:
        return None
    return UserRecord(id=row["id"], email=row["email"])


def get_want_owner(want_id: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT user_id FROM wants WHERE id = ?", (want_id,)).fetchone()
    if row is None or row["user_id"] is None:
        return None
    return str(row["user_id"])


def get_listing_owner(listing_id: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT user_id FROM listings WHERE id = ?", (listing_id,)).fetchone()
    if row is None or row["user_id"] is None:
        return None
    return str(row["user_id"])


def list_active_wants() -> list[WantRecord]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, text, category, area, keywords, status, created_at
            FROM wants
            WHERE status != 'done'
            ORDER BY created_at ASC
            """
        ).fetchall()
    return [
        WantRecord(
            id=row["id"],
            text=row["text"],
            category=row["category"],
            area=row["area"],
            keywords=json.loads(row["keywords"]),
            status=row["status"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def list_negotiation_ids() -> list[str]:
    with connect() as conn:
        rows = conn.execute("SELECT id FROM negotiations ORDER BY id ASC").fetchall()
    return [str(row["id"]) for row in rows]


def upsert_recommendation(want_id: str, listing_id: str, suggested_offer: int, message: str) -> bool:
    """Store a copy-ready offer. Returns True when the row is new."""

    with connect() as conn:
        existing = conn.execute(
            """
            SELECT suggested_offer FROM recommendations
            WHERE want_id = ? AND listing_id = ?
            """,
            (want_id, listing_id),
        ).fetchone()
        if existing is not None:
            return False
        conn.execute(
            """
            INSERT INTO recommendations (want_id, listing_id, suggested_offer, message)
            VALUES (?, ?, ?, ?)
            """,
            (want_id, listing_id, suggested_offer, message),
        )
    return True


def list_recommendations(want_id: str) -> list[RecommendationRow]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT r.listing_id, r.suggested_offer, r.message
            FROM recommendations r
            JOIN listings l ON l.id = r.listing_id
            WHERE r.want_id = ?
            ORDER BY CASE l.origin WHEN 'lister' THEN 0 WHEN 'seed' THEN 1 ELSE 2 END,
                     l.posted_at DESC
            """,
            (want_id,),
        ).fetchall()
    return [
        RecommendationRow(
            listing_id=row["listing_id"],
            suggested_offer=int(row["suggested_offer"]),
            message=row["message"],
        )
        for row in rows
    ]


def secret_numbers() -> set[int]:
    with connect() as conn:
        rows = conn.execute("SELECT buyer_max, seller_min FROM price_limits").fetchall()
        extra = conn.execute("SELECT buyer_ceiling, seller_floor FROM thread_limits").fetchall()
    numbers: set[int] = set()
    for row in rows:
        if row["buyer_max"] is not None:
            numbers.add(int(row["buyer_max"]))
        if row["seller_min"] is not None:
            numbers.add(int(row["seller_min"]))
    for row in extra:
        if row["buyer_ceiling"] is not None:
            numbers.add(int(row["buyer_ceiling"]))
        if row["seller_floor"] is not None:
            numbers.add(int(row["seller_floor"]))
    return numbers


def add_activity(message: str) -> None:
    text = " ".join(message.split())
    if not text:
        return
    with connect() as conn:
        last = conn.execute("SELECT message FROM activity ORDER BY id DESC LIMIT 1").fetchone()
        if last is not None and last["message"] == text:
            return
        conn.execute(
            "INSERT INTO activity (created_at, message) VALUES (?, ?)",
            (_activity_now(), text[:280]),
        )


def list_activity(limit: int = 40) -> list[tuple[str, str]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT created_at, message FROM activity ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [(str(row["created_at"]), str(row["message"])) for row in rows]


def _activity_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def count_origin(origin: str) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM listings WHERE origin = ?",
            (origin,),
        ).fetchone()
    return int(row["n"])


def set_listing_price(listing_id: str, price: int) -> None:
    with connect() as conn:
        conn.execute("UPDATE listings SET price = ? WHERE id = ?", (price, listing_id))


def replace_vetting(listing_id: str, appraisal: Appraisal, inspection: Inspection) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE appraisals
            SET estimated_value = ?, low = ?, high = ?, comps = ?, verdict = ?
            WHERE listing_id = ?
            """,
            (
                appraisal.estimated_value,
                appraisal.low,
                appraisal.high,
                json.dumps([comp.model_dump() for comp in appraisal.comps]),
                appraisal.verdict,
                listing_id,
            ),
        )
        conn.execute(
            """
            UPDATE inspections SET trust_level = ?, signals = ? WHERE listing_id = ?
            """,
            (
                inspection.trust_level,
                json.dumps([signal.model_dump() for signal in inspection.signals]),
                listing_id,
            ),
        )


def list_want_ids_for_user(user_id: str) -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id FROM wants WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [str(row["id"]) for row in rows]


def list_listing_ids_for_user(user_id: str) -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id FROM listings
            WHERE user_id = ? AND origin = 'lister'
            ORDER BY posted_at DESC
            """,
            (user_id,),
        ).fetchall()
    return [str(row["id"]) for row in rows]


def list_negotiations_for_listing(listing_id: str) -> list[Negotiation]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id FROM negotiations WHERE listing_id = ? ORDER BY id ASC",
            (listing_id,),
        ).fetchall()
    found: list[Negotiation] = []
    for row in rows:
        item = get_negotiation(row["id"])
        if item is not None:
            found.append(item)
    return found


def users_watching(listing_id: str) -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT wants.user_id AS user_id
            FROM want_matches
            JOIN wants ON wants.id = want_matches.want_id
            WHERE want_matches.listing_id = ? AND wants.user_id IS NOT NULL
            """,
            (listing_id,),
        ).fetchall()
    return [str(row["user_id"]) for row in rows]


@dataclass(frozen=True)
class NotificationRow:
    id: str
    created_at: str
    kind: str
    message: str
    href: str | None
    unread: bool


def find_open_want(user_id: str, text: str) -> str | None:
    needle = " ".join(text.lower().split())
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, text FROM wants
            WHERE user_id = ? AND status != 'done'
            ORDER BY created_at ASC
            """,
            (user_id,),
        ).fetchall()
    for row in rows:
        if " ".join(str(row["text"]).lower().split()) == needle:
            return str(row["id"])
    return None


def replace_want_token(want_id: str, token_hash: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE want_access SET token_hash = ? WHERE want_id = ?",
            (token_hash, want_id),
        )


def add_notification(
    notification_id: str,
    user_id: str,
    created_at: str,
    kind: str,
    message: str,
    href: str | None,
) -> None:
    with connect() as conn:
        duplicate = conn.execute(
            """
            SELECT 1 FROM notifications
            WHERE user_id = ? AND kind = ? AND message = ?
              AND IFNULL(href, '') = IFNULL(?, '') AND read_at IS NULL
            """,
            (user_id, kind, message, href),
        ).fetchone()
        if duplicate is not None:
            return
        conn.execute(
            """
            INSERT INTO notifications (id, user_id, created_at, kind, message, href, read_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL)
            """,
            (notification_id, user_id, created_at, kind, message, href),
        )


def list_notifications(user_id: str, limit: int = 30) -> list[NotificationRow]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, kind, message, href, read_at
            FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [
        NotificationRow(
            id=row["id"],
            created_at=row["created_at"],
            kind=row["kind"],
            message=row["message"],
            href=row["href"],
            unread=row["read_at"] is None,
        )
        for row in rows
    ]


def unread_count(user_id: str) -> int:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n FROM notifications
            WHERE user_id = ? AND read_at IS NULL
            """,
            (user_id,),
        ).fetchone()
    return int(row["n"])


def mark_notifications_read(user_id: str, ids: list[str] | None, read_at: str) -> None:
    with connect() as conn:
        if ids:
            marks = ",".join("?" for _ in ids)
            conn.execute(
                f"""
                UPDATE notifications SET read_at = ?
                WHERE user_id = ? AND id IN ({marks}) AND read_at IS NULL
                """,
                (read_at, user_id, *ids),
            )
            return
        conn.execute(
            """
            UPDATE notifications SET read_at = ?
            WHERE user_id = ? AND read_at IS NULL
            """,
            (read_at, user_id),
        )
