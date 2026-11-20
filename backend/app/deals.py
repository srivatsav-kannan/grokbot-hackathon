"""One thread per listing and buyer. Private limits stay on the server."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from backend.app.agents.llm import complete, message_effort, message_model, parse_json_reply
from backend.app.agents.negotiator import negotiate
from backend.app.db import connect
from backend.app.errors import APIError
from backend.app.repository import (
    ListingRecord,
    get_limits,
    get_listing,
    get_listing_owner,
    get_want,
    list_want_ids_for_user,
)
from backend.app.schemas import (
    CompletedDeal,
    DealsResponse,
    BuyerBotInbox,
    ListingInbox,
    ThreadMessagePublic,
    ThreadSummary,
    ThreadView,
)
from backend.app.services import _note, _notify, _suggest_offer, source_name_for

_AUTHORS = {"buyer", "buyer_bot", "seller", "seller_bot"}


def _existing_key(user_id: str, scope: str, key: str | None) -> str | None:
    if not key:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT record_id FROM idempotency_keys WHERE user_id = ? AND scope = ? AND key = ?",
            (user_id, scope, key),
        ).fetchone()
    return None if row is None else str(row["record_id"])


def _save_key(user_id: str, scope: str, key: str | None, record_id: str) -> None:
    if not key:
        return
    with connect() as conn:
        already = conn.execute(
            "SELECT record_id FROM idempotency_keys WHERE user_id = ? AND scope = ? AND key = ?",
            (user_id, scope, key),
        ).fetchone()
        if already is None:
            conn.execute(
                """
                INSERT INTO idempotency_keys (user_id, scope, key, record_id)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, scope, key, record_id),
            )


def _last_amount(thread_id: str) -> int | None:
    for _at, _author, _kind, amount, _body in reversed(_messages(thread_id)):
        if amount is not None:
            return int(amount)
    return None


def _is_sold(listing_id: str) -> bool:
    with connect() as conn:
        row = conn.execute("SELECT id FROM completions WHERE listing_id = ?", (listing_id,)).fetchone()
    return row is not None


def _complete(thread_id: str, listing_id: str, price: int) -> None:
    if _is_sold(listing_id):
        with connect() as conn:
            row = conn.execute("SELECT thread_id FROM completions WHERE listing_id = ?", (listing_id,)).fetchone()
        if row is not None and row["thread_id"] == thread_id:
            _set_status(thread_id, "deal")
            return
        _set_status(thread_id, "declined")
        raise APIError(400, "bad_request", "This listing already sold to someone else.")
    buyer = _buyer_id(thread_id)
    seller = get_listing_owner(listing_id)
    if not buyer:
        return
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO completions (id, listing_id, buyer_id, seller_id, thread_id, price, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (_new("cmp_"), listing_id, buyer, seller, thread_id, int(price), _now()),
            )
            conn.execute("UPDATE listings SET status = 'sold' WHERE id = ?", (listing_id,))
    except Exception:  # noqa: BLE001 - a second accept loses the unique race. One record stays.
        if not _is_sold(listing_id):
            raise
    _set_status(thread_id, "deal")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new(prefix: str) -> str:
    return prefix + secrets.token_hex(4)


def _safe_sentence(text: str, *secrets_n: int) -> str:
    cleaned = " ".join(text.split())
    lowered = cleaned.lower()
    if not cleaned or len(cleaned) > 240:
        return ""
    if any(word in lowered for word in ("buyer_max", "seller_min", "price_limits", "maximum", "minimum")):
        return ""
    for number in secrets_n:
        if number and str(number) in cleaned:
            return ""
    return cleaned


def _phrase(listing: ListingRecord, kind: str, amount: int | None, fallback: str, *hidden: int) -> str:
    amount_line = "no dollar amount" if amount is None else str(amount)
    parsed = parse_json_reply(
        complete(
            (
                "Write one short pickup sentence for this turn. "
                "Use only the dollar amount below. Do not invent a budget, maximum, or minimum. "
                'Reply as JSON {"message": "..."}.\n'
                f"Title: {listing.title}\n"
                f"Turn: seller {kind} {amount_line}"
            ),
            model=message_model(),
            effort=message_effort(),
            max_tokens=200,
        )
    )
    if isinstance(parsed, dict) and isinstance(parsed.get("message"), str):
        sentence = _safe_sentence(parsed["message"], *hidden)
        if sentence:
            return sentence
    return fallback


def record_bot_thread(
    listing: ListingRecord,
    buyer_id: str | None,
    want_id: str | None,
    messages,
    outcome: str,
    ceiling: int,
    floor: int,
) -> str | None:
    """Store a finished bot exchange once. Returns the thread id."""

    if not buyer_id:
        return None
    thread_id = _ensure(listing.id, buyer_id, want_id, "bot", "bot", ceiling, floor)
    if _message_count(thread_id):
        return thread_id
    rows = []
    for message in messages:
        author = "buyer_bot" if message.from_ == "buyer" else "seller_bot"
        rows.append((author, message.kind, message.amount, message.text, message.at))
    _append(thread_id, rows)
    # A bot agreement waits for the buyer to approve it. Only approval records a sale.
    status = "agreed" if outcome == "deal" else "declined"
    _set_status(thread_id, status)
    return thread_id


def open_thread(
    user_id: str,
    listing_id: str,
    intent: str,
    text: str | None,
    amount: int | None,
    limit: int | None,
    idempotency_key: str | None = None,
):
    prior = _existing_key(user_id, "thread", idempotency_key)
    if prior:
        return _view(prior, user_id)
    listing = _require_listing(listing_id)
    if listing.origin == "scout":
        raise APIError(400, "bad_request", "This listing is on another site. Copy the suggested message instead.")
    if get_listing_owner(listing_id) == user_id:
        raise APIError(400, "bad_request", "This is your listing. Offers on it show up in Deals.")
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM threads WHERE listing_id = ? AND buyer_id = ?", (listing_id, user_id)
        ).fetchone()
    if existing is not None and _message_count(str(existing["id"])):
        # One thread per listing and buyer. Opening again just returns it.
        thread_id = str(existing["id"])
        if limit is not None:
            with connect() as conn:
                conn.execute("UPDATE thread_limits SET buyer_ceiling = ? WHERE thread_id = ?", (limit, thread_id))
        _save_key(user_id, "thread", idempotency_key, thread_id)
        return _view(thread_id, user_id)
    if _is_sold(listing_id):
        raise APIError(400, "bad_request", "This listing is already sold.")
    limits = get_limits(listing_id)
    floor = limits.seller_min if limits is not None else max(1, listing.price // 2)
    ceiling = limit if limit is not None else listing.price
    want_id = None
    thread_id = _ensure(listing_id, user_id, want_id, "manual", "bot", ceiling, floor)
    if intent == "bot":
        _set_mode(thread_id, "buyer", "bot")
        if not _message_count(thread_id):
            draft = negotiate(listing, ceiling, floor)
            record_bot_thread(listing, user_id, None, draft.messages, draft.outcome, ceiling, floor)
            _note(f"A buyer bot talked with the seller of {listing.title}")
            _notify(get_listing_owner(listing_id), "offer", f"A buyer bot opened a talk on {listing.title}", f"/deals/{thread_id}")
    elif intent == "offer":
        _set_mode(thread_id, "buyer", "manual")
        body = (text or "").strip() or (f"I can offer {amount}." if amount is not None else "I'd like to buy this.")
        _append(thread_id, [("buyer", "offer" if amount is not None else "text", amount, body, _now())])
        _reply_if_bot(thread_id, listing, ceiling, floor)
        _notify(get_listing_owner(listing_id), "offer", f"A buyer wrote on {listing.title}", f"/deals/{thread_id}")
    else:
        _set_mode(thread_id, "buyer", "manual")
        body = (text or "").strip() or "Is this still available?"
        _append(thread_id, [("buyer", "text", amount, body, _now())])
        _reply_if_bot(thread_id, listing, ceiling, floor)
    _save_key(user_id, "thread", idempotency_key, thread_id)
    return _view(thread_id, user_id)


def post_message(
    user_id: str,
    thread_id: str,
    text: str,
    amount: int | None,
    kind: str,
    idempotency_key: str | None = None,
):
    prior = _existing_key(user_id, "message", idempotency_key)
    if prior:
        return _view(prior, user_id)
    role = _role(thread_id, user_id)
    listing = _require_listing(_listing_id(thread_id))
    if _thread_status(thread_id) == "deal" or (kind == "accept" and _is_sold(listing.id)):
        _save_key(user_id, "message", idempotency_key, thread_id)
        return _view(thread_id, user_id)
    if kind == "accept" and _last_amount(thread_id) is None and amount is None:
        raise APIError(400, "bad_request", "There is no offer to accept yet.")
    author = "buyer" if role == "buyer" else "seller"
    body = text.strip() or ("Here is my number." if amount is not None else "Okay.")
    _append(thread_id, [(author, kind, amount, body, _now())])
    if kind == "accept":
        price = amount if amount is not None else _last_amount(thread_id) or listing.price
        _complete(thread_id, listing.id, price)
        _notify(_other_user(thread_id, role), "deal", f"A deal was accepted on {listing.title}", f"/deals/{thread_id}")
        _note(f"Sold {listing.title}")
    elif kind == "decline":
        _set_status(thread_id, "declined")
    else:
        _set_status(thread_id, "open")
        ceiling, floor = _limits(thread_id)
        _reply_if_bot(thread_id, listing, ceiling, floor)
        if kind in {"offer", "counter"}:
            _notify(
                _other_user(thread_id, role),
                "counteroffer" if kind == "counter" else "offer",
                f"New message on {listing.title}",
                f"/deals/{thread_id}",
            )
    _save_key(user_id, "message", idempotency_key, thread_id)
    return _view(thread_id, user_id)


def set_mode(user_id: str, thread_id: str, mode: str):
    role = _role(thread_id, user_id)
    _set_mode(thread_id, role, mode)
    listing = _require_listing(_listing_id(thread_id))
    ceiling, floor = _limits(thread_id)
    if mode == "bot":
        _reply_if_bot(thread_id, listing, ceiling, floor)
    return _view(thread_id, user_id)


def set_limit(user_id: str, thread_id: str, limit: int):
    role = _role(thread_id, user_id)
    with connect() as conn:
        if role == "buyer":
            conn.execute("UPDATE thread_limits SET buyer_ceiling = ? WHERE thread_id = ?", (limit, thread_id))
        else:
            conn.execute("UPDATE thread_limits SET seller_floor = ? WHERE thread_id = ?", (limit, thread_id))
            listing_id = _listing_id(thread_id)
            conn.execute(
                """
                UPDATE price_limits SET seller_min = ?
                WHERE listing_id = ? AND want_id IS NULL
                """,
                (limit, listing_id),
            )
    return _view(thread_id, user_id)


def thread_for(user_id: str, thread_id: str) -> ThreadView:
    _role(thread_id, user_id)
    return _view(thread_id, user_id)


def inbox(user_id: str) -> DealsResponse:
    rows = _rows_for_user(user_id)
    bots: dict[str, BuyerBotInbox] = {}
    direct: list[ThreadSummary] = []
    listings: dict[str, ListingInbox] = {}
    for row in rows:
        summary = _summary_row(row, user_id)
        if row["buyer_id"] == user_id and row["want_id"]:
            label = row["want_text"] or "Buyer bot"
            bucket = bots.setdefault(
                row["want_id"],
                BuyerBotInbox(id=row["want_id"], label=label, threads=[]),
            )
            bucket.threads.append(summary)
        elif row["buyer_id"] == user_id:
            direct.append(summary)
        if row["seller_id"] == user_id:
            box = listings.setdefault(
                row["listing_id"],
                ListingInbox(listing_id=row["listing_id"], title=row["title"], threads=[]),
            )
            box.threads.append(summary)
    from backend.app.services import _want_view

    ordered: list[BuyerBotInbox] = []
    for want_id in list_want_ids_for_user(user_id):
        record = get_want(want_id)
        bucket = bots.pop(want_id, None) or BuyerBotInbox(
            id=want_id,
            label=record.text if record is not None else "Buyer bot",
            threads=[],
        )
        if record is not None:
            bucket.status = record.status
            bucket.created_at = record.created_at
            try:
                bucket.matches = _want_view(want_id).matches
            except APIError:
                bucket.matches = []
        ordered.append(bucket)
    ordered.extend(bots.values())
    ordered.sort(key=lambda bot: bot.created_at or "", reverse=True)
    with connect() as conn:
        done = conn.execute(
            """
            SELECT completions.*, listings.title FROM completions
            JOIN listings ON listings.id = completions.listing_id
            WHERE completions.buyer_id = ? OR completions.seller_id = ?
            ORDER BY completions.created_at DESC
            """,
            (user_id, user_id),
        ).fetchall()
    completed = [
        CompletedDeal(
            id=str(row["id"]),
            listing_id=str(row["listing_id"]),
            title=str(row["title"]),
            price=int(row["price"]),
            role="buyer" if row["buyer_id"] == user_id else "seller",
            thread_id=row["thread_id"],
            at=str(row["created_at"]),
        )
        for row in done
    ]
    return DealsResponse(
        buyer_bots=ordered,
        direct=direct,
        listings=list(listings.values()),
        completed=completed,
    )


def _require_listing(listing_id: str) -> ListingRecord:
    listing = get_listing(listing_id)
    if listing is None:
        raise APIError(404, "not_found", "Listing not found.")
    return listing


def _ensure(listing_id: str, buyer_id: str, want_id: str | None, buyer_mode: str, seller_mode: str, ceiling: int, floor: int) -> str:
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM threads WHERE listing_id = ? AND buyer_id = ?",
            (listing_id, buyer_id),
        ).fetchone()
        if row is not None:
            if want_id:
                conn.execute("UPDATE threads SET want_id = COALESCE(want_id, ?) WHERE id = ?", (want_id, row["id"]))
            conn.execute(
                """
                INSERT INTO thread_limits (thread_id, buyer_ceiling, seller_floor)
                VALUES (?, ?, ?)
                ON CONFLICT(thread_id) DO UPDATE SET
                    buyer_ceiling = COALESCE(thread_limits.buyer_ceiling, excluded.buyer_ceiling),
                    seller_floor = COALESCE(thread_limits.seller_floor, excluded.seller_floor)
                """,
                (row["id"], ceiling, floor),
            )
            return str(row["id"])
        thread_id = _new("thr_")
        now = _now()
        conn.execute(
            """
            INSERT INTO threads (
                id, listing_id, buyer_id, want_id, buyer_mode, seller_mode, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?)
            """,
            (thread_id, listing_id, buyer_id, want_id, buyer_mode, seller_mode, now, now),
        )
        conn.execute(
            "INSERT INTO thread_limits (thread_id, buyer_ceiling, seller_floor) VALUES (?, ?, ?)",
            (thread_id, ceiling, floor),
        )
    return thread_id


def _append(thread_id: str, rows: list[tuple]) -> None:
    now = _now()
    with connect() as conn:
        for author, kind, amount, body, at in rows:
            if author not in _AUTHORS:
                continue
            conn.execute(
                """
                INSERT INTO thread_messages (thread_id, at, author, kind, amount, body)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (thread_id, at or now, author, kind, amount, body),
            )
        conn.execute("UPDATE threads SET updated_at = ? WHERE id = ?", (now, thread_id))


def _message_count(thread_id: str) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM thread_messages WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
    return int(row["n"])


def _thread_status(thread_id: str) -> str:
    with connect() as conn:
        row = conn.execute("SELECT status FROM threads WHERE id = ?", (thread_id,)).fetchone()
    return "" if row is None else str(row["status"])


def _set_status(thread_id: str, status: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE threads SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), thread_id),
        )


def _set_mode(thread_id: str, role: str, mode: str) -> None:
    column = "buyer_mode" if role == "buyer" else "seller_mode"
    with connect() as conn:
        conn.execute(
            f"UPDATE threads SET {column} = ?, updated_at = ? WHERE id = ?",
            (mode, _now(), thread_id),
        )


def _limits(thread_id: str) -> tuple[int, int]:
    with connect() as conn:
        row = conn.execute(
            "SELECT buyer_ceiling, seller_floor FROM thread_limits WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
    if row is None:
        return (1, 1)
    return (int(row["buyer_ceiling"] or 1), int(row["seller_floor"] or 1))


def _listing_id(thread_id: str) -> str:
    with connect() as conn:
        row = conn.execute("SELECT listing_id FROM threads WHERE id = ?", (thread_id,)).fetchone()
    if row is None:
        raise APIError(404, "not_found", "Thread not found.")
    return str(row["listing_id"])


def _role(thread_id: str, user_id: str) -> str:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT threads.buyer_id, listings.user_id AS seller_id
            FROM threads JOIN listings ON listings.id = threads.listing_id
            WHERE threads.id = ?
            """,
            (thread_id,),
        ).fetchone()
    if row is None:
        raise APIError(404, "not_found", "Thread not found.")
    if row["buyer_id"] == user_id:
        return "buyer"
    if row["seller_id"] == user_id:
        return "seller"
    raise APIError(401, "unauthorized", "Sign in to open this thread.")


def _other_user(thread_id: str, role: str) -> str | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT threads.buyer_id, listings.user_id AS seller_id
            FROM threads JOIN listings ON listings.id = threads.listing_id
            WHERE threads.id = ?
            """,
            (thread_id,),
        ).fetchone()
    if row is None:
        return None
    return str(row["seller_id"]) if role == "buyer" and row["seller_id"] else (
        str(row["buyer_id"]) if role == "seller" else None
    )


def _messages(thread_id: str) -> list[tuple]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT at, author, kind, amount, body
            FROM thread_messages WHERE thread_id = ? ORDER BY id ASC
            """,
            (thread_id,),
        ).fetchall()
    return [(row["at"], row["author"], row["kind"], row["amount"], row["body"]) for row in rows]


def _reply_if_bot(thread_id: str, listing: ListingRecord, ceiling: int, floor: int) -> None:
    messages = _messages(thread_id)
    if not messages:
        return
    _at, author, _kind, amount, _body = messages[-1]
    with connect() as conn:
        modes = conn.execute(
            "SELECT buyer_mode, seller_mode, status FROM threads WHERE id = ?",
            (thread_id,),
        ).fetchone()
    if modes is None or modes["status"] != "open":
        return
    if author.startswith("buyer") and modes["seller_mode"] == "bot":
        kind, reply_amount, text = _seller_line(listing, amount, ceiling, floor)
        _append(thread_id, [("seller_bot", kind, reply_amount, text, _now())])
        if kind == "accept":
            price = reply_amount if reply_amount is not None else listing.price
            _complete(thread_id, listing.id, price)
            _notify(_buyer_id(thread_id), "deal", f"The seller bot accepted on {listing.title}", f"/deals/{thread_id}")
        elif kind == "counter":
            _notify(_buyer_id(thread_id), "counteroffer", f"The seller bot countered on {listing.title}", f"/deals/{thread_id}")
    elif author.startswith("seller") and modes["buyer_mode"] == "bot":
        kind, reply_amount, text = _buyer_line(listing, amount, ceiling, floor)
        _append(thread_id, [("buyer_bot", kind, reply_amount, text, _now())])
        if kind == "accept":
            _set_status(thread_id, "agreed")
            _notify(_buyer_id(thread_id), "deal", f"Your bot agreed on {listing.title}. Approve to buy.", f"/deals/{thread_id}")


def _buyer_id(thread_id: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT buyer_id FROM threads WHERE id = ?", (thread_id,)).fetchone()
    return None if row is None else str(row["buyer_id"])


def _seller_line(listing: ListingRecord, amount: int | None, ceiling: int, floor: int):
    hidden = {ceiling, floor}
    if amount is None or amount < floor:
        counter = floor + 1
        while counter in hidden:
            counter += 1
        if amount is not None and counter <= amount:
            return ("decline", None, "I have to pass on that offer.")
        text = _phrase(listing, "counter", counter, f"I could meet you at {counter}.", ceiling, floor)
        return ("counter", counter, text)
    if amount in hidden:
        return ("accept", None, "That works. Pickup this week.")
    text = _phrase(listing, "accept", amount, f"That works at {amount}. Pickup this week.", ceiling, floor)
    return ("accept", amount, text)


def _buyer_line(listing: ListingRecord, amount: int | None, ceiling: int, floor: int):
    hidden = {ceiling, floor}
    if amount is not None and amount <= ceiling and amount not in hidden:
        text = _phrase(listing, "accept", amount, f"I can do {amount}.", ceiling, floor)
        return ("accept", amount, text)
    offer = min(ceiling - 1, listing.price) if ceiling > 1 else None
    if offer is None or offer in hidden or offer < 1:
        return ("decline", None, "I have to pass on that offer.")
    text = _phrase(listing, "offer", offer, f"I can do {offer}.", ceiling, floor)
    return ("offer", offer, text)


def _view(thread_id: str, user_id: str) -> ThreadView:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT threads.*, listings.title, listings.price, listings.origin, wants.text AS want_text
            FROM threads
            JOIN listings ON listings.id = threads.listing_id
            LEFT JOIN wants ON wants.id = threads.want_id
            WHERE threads.id = ?
            """,
            (thread_id,),
        ).fetchone()
    if row is None:
        raise APIError(404, "not_found", "Thread not found.")
    role = "buyer" if row["buyer_id"] == user_id else "seller"
    ceiling, floor = _limits(thread_id)
    messages = [
        ThreadMessagePublic(at=at, author=author, kind=kind, amount=amount, text=body)
        for at, author, kind, amount, body in _messages(thread_id)
    ]
    return ThreadView(
        id=row["id"],
        listing_id=row["listing_id"],
        listing_title=row["title"],
        listing_price=row["price"],
        origin=row["origin"],
        role=role,  # type: ignore[arg-type]
        want_id=row["want_id"],
        want_label=row["want_text"],
        buyer_mode=row["buyer_mode"],
        seller_mode=row["seller_mode"],
        status=row["status"],
        summary=_summary(row["status"], messages, role, row["buyer_mode"] if role == "buyer" else row["seller_mode"]),
        messages=messages,
        my_limit=ceiling if role == "buyer" else floor,
    )


def _summary(status: str, messages: list[ThreadMessagePublic], role: str, my_mode: str) -> str:
    if status == "deal":
        return "Sold" if role == "seller" else "Bought"
    if status == "agreed":
        price = next((m.amount for m in reversed(messages) if m.amount is not None), None)
        at = f" at ${price}" if price is not None else ""
        return f"Bot agreed{at}. Approve to buy" if role == "buyer" else f"Buyer's bot agreed{at}. Waiting on the buyer"
    if status == "declined":
        return "Passed"
    if not messages:
        return "Waiting on you" if my_mode == "manual" else "Bot is negotiating"
    last = messages[-1]
    mine = last.author.startswith("buyer" if role == "buyer" else "seller")
    if not mine and my_mode == "manual":
        return "Waiting on you"
    if last.author.endswith("_bot") and last.amount is not None and last.kind in {"offer", "counter"}:
        verb = "countering" if last.kind == "counter" else "offering"
        return f"Bot {verb} at ${last.amount}"
    if my_mode == "bot":
        return "Bot is negotiating"
    return "Waiting on them"


def _rows_for_user(user_id: str):
    with connect() as conn:
        return conn.execute(
            """
            SELECT threads.*, listings.title, listings.user_id AS seller_id, wants.text AS want_text
            FROM threads
            JOIN listings ON listings.id = threads.listing_id
            LEFT JOIN wants ON wants.id = threads.want_id
            WHERE threads.buyer_id = ? OR listings.user_id = ?
            ORDER BY threads.updated_at DESC
            """,
            (user_id, user_id),
        ).fetchall()


def _summary_row(row, user_id: str) -> ThreadSummary:
    role = "buyer" if row["buyer_id"] == user_id else "seller"
    messages = [
        ThreadMessagePublic(at=at, author=author, kind=kind, amount=amount, text=body)
        for at, author, kind, amount, body in _messages(row["id"])
    ]
    mode = row["buyer_mode"] if role == "buyer" else row["seller_mode"]
    return ThreadSummary(
        id=row["id"],
        listing_id=row["listing_id"],
        title=row["title"],
        summary=_summary(row["status"], messages, role, mode),
        updated_at=row["updated_at"],
    )


def suggestion_for(listing: ListingRecord):
    """Public paste-ready offer for a scouted listing. Not a private limit."""

    limits = get_limits(listing.id)
    floor = limits.seller_min if limits is not None else None
    amount = _suggest_offer(listing.price, None, floor)
    source = source_name_for(listing.origin, listing.source_url)
    return amount, (
        f"Hi — I saw {listing.title} on {source}. "
        f"I can offer ${amount} and pick it up in the Bay Area. Is it still available?"
    )
