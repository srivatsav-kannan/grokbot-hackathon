"""Routes call these functions. Agents and the database stay behind them.

Person C (@heruirayli) owns this file. Call the agent functions; do not rewrite
their decisions here. Private ceilings and token hashes stay inside this module
and the repository. They are not fields on the objects returned below.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
from collections import Counter
from dataclasses import replace
from urllib.parse import urlparse

from backend.app import repository as repo
from backend.app.agents.appraiser import appraise
from backend.app.agents.buyer import (
    MAX_HUNT_MATCHES,
    WantCriteria,
    match_listings,
    parse_want,
    private_max_from_text,
    redact_money,
)
from backend.app.agents.inspector import inspect
from backend.app.agents.lister import draft_from_photo
from backend.app.agents.llm import complete, message_effort, message_model, parse_json_reply
from backend.app.agents.negotiator import negotiate
from backend.app.agents.scout import ScoutStopped, scout_query, scout_run
from backend.app.errors import APIError
from backend.app.repository import Limits, ListingRecord
from backend.app.schemas import (
    CATEGORIES,
    AppraisalSummary,
    InspectionSummary,
    ListerResponse,
    ListingCard,
    ListingDetail,
    ListingListResponse,
    Negotiation,
    PublishListingRequest,
    ScoutReport,
    ScoutRunResponse,
    ActivityResponse,
    ActivityEvent,
    BotsResponse,
    BuyerBot,
    NotificationPublic,
    NotificationsResponse,
    RecommendationPublic,
    SearchResponse,
    SellerBot,
    UserPublic,
    WantCreated,
    WantCriteriaPublic,
    WantMatchPublic,
    WantView,
)

log = logging.getLogger("fairlot")
SESSION_COOKIE = "fairlot_session"
_FORBIDDEN_WORDS = (
    "buyer_max",
    "seller_min",
    "price_limits",
    "access_token",
    "max_price",
    "password",
)


# Hunt opens negotiations on listings asking up to this multiple of the buyer's
# ceiling. The negotiator still never offers more than the ceiling itself.
HUNT_STRETCH = 1.25


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return prefix + secrets.token_hex(4)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def limits_for_asking_price(price: int, min_price: int | None = None) -> Limits:
    """Server-side policy for a listing a person just published. Not returned.

    The numbers are a seller floor and a fallback buyer ceiling for the
    on-site negotiate endpoint. A want uses its own stored ceiling instead.
    A seller-supplied minimum wins over the default floor, capped at the
    asking price.
    """

    if min_price is not None:
        seller_min = max(1, min(int(min_price), price - 1))
    else:
        seller_min = max(1, int(round(price * 0.75)))
    buyer_max = max(seller_min, int(round(price * 0.95)))
    return Limits(buyer_max=buyer_max, seller_min=seller_min)


def source_name_for(origin: str, source_url: str | None) -> str:
    if origin == "lister":
        return "Fairlot"
    if origin == "seed":
        return ""
    blob = (source_url or "").lower()
    for needle, label in (
        ("craigslist", "Craigslist"),
        ("ebay", "eBay"),
        ("offerup", "OfferUp"),
        ("facebook", "Facebook"),
        ("mercari", "Mercari"),
        ("nextdoor", "Nextdoor"),
    ):
        if needle in blob:
            return label
    host = ""
    if source_url:
        host = (urlparse(source_url).hostname or "").removeprefix("www.")
    return host or "another marketplace"


def _note(message: str) -> None:
    """Public activity line. Drops anything that might carry a private limit."""

    lowered = message.lower()
    if any(word in lowered for word in _FORBIDDEN_WORDS):
        return
    for number in repo.secret_numbers():
        if str(number) in message:
            return
    repo.add_activity(message)


def _suggest_offer(ask: int, ceiling: int | None, floor: int | None) -> int:
    """A public offer that is not itself a stored ceiling or floor."""

    forbidden = {number for number in (ceiling, floor) if isinstance(number, int)}
    candidate = ask if ask > 0 else 1
    if ceiling is not None:
        candidate = min(candidate, max(1, ceiling - 1))
    hops = 0
    while candidate in forbidden and hops < 80:
        candidate -= 1
        hops += 1
        if candidate < 1:
            candidate = max(ask, 1) + 1
            break
    while candidate in forbidden:
        candidate += 1
        if candidate > ask + 200:
            break
    return max(1, candidate)


def _require_category(category: str | None) -> None:
    if category is not None and category not in CATEGORIES:
        raise APIError(400, "bad_request", "Category must be bikes, computers, or furniture.")


def _card(listing: ListingRecord) -> ListingCard:
    appraisal = repo.get_appraisal(listing.id)
    inspection = repo.get_inspection(listing.id)
    if appraisal is None or inspection is None:
        raise APIError(404, "not_found", "Listing not found.")
    return ListingCard(
        id=listing.id,
        category=listing.category,  # type: ignore[arg-type]
        title=listing.title,
        price=listing.price,
        photos=listing.photos,
        neighborhood=listing.neighborhood,
        posted_at=listing.posted_at,
        origin=listing.origin,  # type: ignore[arg-type]
        source_name=source_name_for(listing.origin, listing.source_url),
        appraisal=AppraisalSummary(
            estimated_value=appraisal.estimated_value,
            verdict=appraisal.verdict,
        ),
        inspection=InspectionSummary(trust_level=inspection.trust_level),
    )


def _detail(listing: ListingRecord) -> ListingDetail:
    appraisal = repo.get_appraisal(listing.id)
    inspection = repo.get_inspection(listing.id)
    if appraisal is None or inspection is None:
        raise APIError(404, "not_found", "Listing not found.")
    return ListingDetail(
        id=listing.id,
        category=listing.category,  # type: ignore[arg-type]
        title=listing.title,
        price=listing.price,
        photos=listing.photos,
        neighborhood=listing.neighborhood,
        posted_at=listing.posted_at,
        origin=listing.origin,  # type: ignore[arg-type]
        source_name=source_name_for(listing.origin, listing.source_url),
        description=listing.description,
        source_url=listing.source_url,
        appraisal=appraisal,
        inspection=inspection,
    )


def list_listings(category: str | None, q: str | None, kind: str | None = None) -> ListingListResponse:
    _require_category(category)
    if kind is not None and kind not in {"native", "external", "sample"}:
        raise APIError(400, "bad_request", "Kind must be native, external, or sample.")
    text = q.strip() if q else None
    rows = repo.list_listings(category, text or None, kind)
    return ListingListResponse(listings=[_card(row) for row in rows])


def get_listing(listing_id: str) -> ListingDetail:
    listing = repo.get_listing(listing_id)
    if listing is None:
        raise APIError(404, "not_found", "Listing not found.")
    return _detail(listing)


def create_draft(photo: bytes, filename: str | None) -> ListerResponse:
    if not photo:
        raise APIError(400, "bad_request", "Choose a photo first.")
    if len(photo) > 2_000_000:
        raise APIError(400, "bad_request", "Photo must be under 2 MB.")
    return ListerResponse(draft=draft_from_photo(photo, filename))


def publish_listing(body: PublishListingRequest, user_id: str) -> ListingDetail:
    title = body.title.strip()
    description = body.description.strip()
    neighborhood = body.neighborhood.strip()
    if not title or not description or not neighborhood:
        raise APIError(400, "bad_request", "Title, description, and neighborhood are required.")
    listing = ListingRecord(
        id=_new_id("lst_"),
        category=body.category,
        title=title,
        description=description,
        price=body.price,
        photos=body.photos,
        neighborhood=neighborhood,
        source_url=None,
        posted_at=_now_iso(),
        origin="lister",
    )
    appraisal = appraise(listing)
    inspection = inspect(listing, appraisal)
    limits = limits_for_asking_price(body.price)
    if body.minimum is not None:
        limits = Limits(buyer_max=max(limits.buyer_max, body.minimum), seller_min=body.minimum)
    repo.insert_listing(listing, appraisal, inspection, limits, user_id=user_id)
    _note(f"Lister published {listing.title} on Fairlot")
    return _detail(listing)


def _negotiate_and_store(
    listing: ListingRecord,
    buyer_max: int,
    seller_min: int,
    want_id: str | None = None,
    user_id: str | None = None,
) -> Negotiation:
    draft = negotiate(listing, buyer_max, seller_min)
    item = Negotiation(
        id=_new_id("neg_"),
        listing_id=listing.id,
        want_id=want_id,
        status="closed",
        outcome=draft.outcome,
        accepted=False,
        messages=draft.messages,
    )
    repo.insert_negotiation(item, user_id=user_id)
    amount = next((message.amount for message in item.messages if message.amount), None)
    if amount is None:
        _note(f"Buyer agent talked with the seller of {listing.title}")
    else:
        _note(f"Buyer agent offered ${amount} on {listing.title}")
    _announce_talk(listing, item)
    return item


def start_negotiation(listing_id: str, user_id: str) -> Negotiation:
    """On-site offer. Uses the listing's stored ceiling, not a client-supplied one."""

    listing = repo.get_listing(listing_id)
    if listing is None:
        raise APIError(404, "not_found", "Listing not found.")
    limits = repo.get_limits(listing_id)
    if limits is None:
        raise APIError(404, "not_found", "Negotiation is not available for this listing.")
    return _negotiate_and_store(listing, limits.buyer_max, limits.seller_min, user_id=user_id)


def get_negotiation(negotiation_id: str) -> Negotiation:
    item = repo.get_negotiation(negotiation_id)
    if item is None:
        raise APIError(404, "not_found", "Negotiation not found.")
    return item


def _ingest_scouted(listings: list[ListingRecord]) -> int:
    """Store new public listings once. The same source id is skipped, not duplicated."""

    added = 0
    added_listings: list[ListingRecord] = []
    for listing in listings:
        existing = repo.get_listing(listing.id)
        if existing is not None:
            if listing.price < existing.price:
                repo.set_listing_price(listing.id, listing.price)
                refreshed = replace(existing, price=listing.price)
                appraisal = appraise(refreshed)
                inspection = inspect(refreshed, appraisal)
                repo.replace_vetting(listing.id, appraisal, inspection)
                _notify_price_drop(existing, listing.price)
            continue
        appraisal = appraise(listing)
        inspection = inspect(listing, appraisal)
        repo.insert_listing(listing, appraisal, inspection, limits_for_asking_price(listing.price))
        if repo.get_listing(listing.id) is None:
            continue
        added += 1
        added_listings.append(listing)
        if inspection.signals:
            reason = " ".join(inspection.signals[0].reason.split())
            _note(f"Inspector flagged {listing.title}: {reason}")
    if added_listings:
        counts: Counter[tuple[str, str]] = Counter()
        for listing in added_listings:
            counts[(listing.category, source_name_for(listing.origin, listing.source_url))] += 1
        for (category, label), count in counts.items():
            _note(f"Scout found {count} new {category} on {label}")
    return added


def run_scout(categories: list[str]) -> ScoutRunResponse:
    for category in categories:
        _require_category(category)
    try:
        result = scout_run(categories)
    except ScoutStopped as exc:
        _note(f"Scout stopped: {exc.reason}. {exc.message}")
        return ScoutRunResponse(
            added=0,
            cached=repo.count_listings(),
            stopped=True,
            report=ScoutReport(reason=exc.reason, message=exc.message),  # type: ignore[arg-type]
        )
    added = _ingest_scouted(list(result.listings))
    if result.stopped and result.report is not None:
        _note(f"Scout stopped: {result.report.reason}. {result.report.message}")
    return ScoutRunResponse(
        added=added,
        cached=repo.count_listings(),
        stopped=result.stopped,
        report=result.report,
    )


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def _check_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split("$", 2)
        if scheme != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(digest, expected)


def _normalize_email(email: str) -> str:
    cleaned = email.strip().lower()
    if " " in cleaned or cleaned.count("@") != 1 or cleaned.startswith("@") or cleaned.endswith("@"):
        raise APIError(400, "bad_request", "Enter an email and a password.")
    local, _, domain = cleaned.partition("@")
    if not local or "." not in domain:
        raise APIError(400, "bad_request", "Enter an email and a password.")
    return cleaned


def user_from_credentials(authorization: str | None, cookie_token: str | None) -> repo.UserRecord | None:
    token = cookie_token
    if authorization:
        scheme, _, rest = authorization.partition(" ")
        bearer = rest.strip()
        if scheme.lower() == "bearer" and bearer.startswith("ses_"):
            token = bearer
    if not token or not token.startswith("ses_"):
        return None
    return repo.user_for_session(_hash_token(token))


def require_user(authorization: str | None, cookie_token: str | None) -> repo.UserRecord:
    user = user_from_credentials(authorization, cookie_token)
    if user is None:
        raise APIError(401, "unauthorized", "Sign in to continue.")
    return user


def signup(email: str, password: str) -> tuple[UserPublic, str]:
    cleaned = _normalize_email(email)
    if repo.get_user_by_email(cleaned) is not None:
        raise APIError(400, "bad_request", "An account with that email already exists.")
    user_id = _new_id("usr_")
    repo.insert_user(user_id, cleaned, _hash_password(password), _now_iso())
    token = "ses_" + secrets.token_urlsafe(32)
    repo.insert_session(_hash_token(token), user_id, _now_iso())
    return UserPublic(id=user_id, email=cleaned), token


def login(email: str, password: str) -> tuple[UserPublic, str]:
    cleaned = _normalize_email(email)
    found = repo.get_user_by_email(cleaned)
    if found is None or not _check_password(password, found[1]):
        raise APIError(401, "unauthorized", "Email or password is wrong.")
    user = found[0]
    token = "ses_" + secrets.token_urlsafe(32)
    repo.insert_session(_hash_token(token), user.id, _now_iso())
    return UserPublic(id=user.id, email=user.email), token


def logout(authorization: str | None, cookie_token: str | None) -> str | None:
    """Delete the presented session. Returns the raw token so the cookie can be cleared."""

    token = cookie_token if cookie_token and cookie_token.startswith("ses_") else None
    if authorization:
        scheme, _, rest = authorization.partition(" ")
        bearer = rest.strip()
        if scheme.lower() == "bearer" and bearer.startswith("ses_"):
            token = bearer
    if token:
        repo.delete_session(_hash_token(token))
    return token


def current_user(authorization: str | None, cookie_token: str | None) -> UserPublic:
    user = require_user(authorization, cookie_token)
    return UserPublic(id=user.id, email=user.email)


def _authorize(want_id: str, token: str, session: repo.UserRecord | None = None) -> None:
    if repo.get_want(want_id) is None:
        raise APIError(404, "not_found", "Want not found.")
    if token:
        digest = repo.get_token_hash(want_id)
        if digest is not None and secrets.compare_digest(digest, _hash_token(token)):
            return
        raise APIError(401, "unauthorized", "Want token required.")
    owner = repo.get_want_owner(want_id)
    if session is not None and owner is not None and session.id == owner:
        return
    raise APIError(401, "unauthorized", "Want token required.")


def _want_token(authorization: str | None) -> str:
    """Bearer want token. An explicit bearer that is not a session is the want token."""

    if not authorization:
        return ""
    scheme, _, rest = authorization.partition(" ")
    token = rest.strip()
    if scheme.lower() != "bearer" or not token or token.startswith("ses_"):
        return ""
    return token


def _criteria_public(record: repo.WantRecord) -> WantCriteriaPublic:
    return WantCriteriaPublic(
        category=record.category,  # type: ignore[arg-type]
        area=record.area,
        keywords=record.keywords,
    )


def _want_view(want_id: str) -> WantView:
    record = repo.get_want(want_id)
    if record is None:
        raise APIError(404, "not_found", "Want not found.")
    matches: list[WantMatchPublic] = []
    for row in repo.list_want_matches(want_id):
        listing = repo.get_listing(row.listing_id)
        if listing is None:
            continue
        appraisal = repo.get_appraisal(listing.id)
        inspection = repo.get_inspection(listing.id)
        if appraisal is None or inspection is None:
            continue
        matches.append(
            WantMatchPublic(
                listing_id=listing.id,
                score=row.score,
                reason=row.reason,
                title=listing.title,
                price=listing.price,
                origin=listing.origin,  # type: ignore[arg-type]
                source_name=source_name_for(listing.origin, listing.source_url),
                source_url=listing.source_url,
                appraisal=AppraisalSummary(
                    estimated_value=appraisal.estimated_value,
                    verdict=appraisal.verdict,
                ),
                inspection=InspectionSummary(trust_level=inspection.trust_level),
            )
        )
    recommendations: list[RecommendationPublic] = []
    for advice in repo.list_recommendations(want_id):
        listing = repo.get_listing(advice.listing_id)
        if listing is None:
            continue
        recommendations.append(
            RecommendationPublic(
                listing_id=listing.id,
                title=listing.title,
                source_name=source_name_for(listing.origin, listing.source_url),
                source_url=listing.source_url,
                suggested_offer=advice.suggested_offer,
                message=advice.message,
            )
        )
    return WantView(
        id=record.id,
        text=record.text,
        criteria=_criteria_public(record),
        status=record.status,  # type: ignore[arg-type]
        matches=matches,
        negotiations=repo.list_negotiations_for_want(want_id),
        recommendations=recommendations,
    )


def create_want(
    text: str,
    category: str | None,
    area: str | None,
    max_price: int | None,
    user_id: str,
) -> WantCreated:
    raw = text.strip()
    if not raw:
        raise APIError(400, "bad_request", "Describe what you want.")
    _require_category(category)
    ceiling = max_price if max_price is not None else private_max_from_text(raw)
    parsed = parse_want(raw)
    chosen_category = category or parsed.category
    chosen_area = area.strip() if area else parsed.area
    _require_category(chosen_category)
    criteria = WantCriteria(
        category=chosen_category,
        area=chosen_area,
        keywords=parsed.keywords,
    )
    token = "tok_" + secrets.token_urlsafe(24)
    existing_id = repo.find_open_want(user_id, raw)
    if existing_id is not None:
        repo.replace_want_token(existing_id, _hash_token(token))
        record = repo.get_want(existing_id)
        status = record.status if record is not None else "open"
        return WantCreated(id=existing_id, access_token=token, status=status)  # type: ignore[arg-type]
    want_id = _new_id("wnt_")
    repo.insert_want(
        want_id=want_id,
        text=raw,
        category=criteria.category,
        area=criteria.area,
        keywords=criteria.keywords,
        status="open",
        created_at=_now_iso(),
        max_price=ceiling,
        token_hash=_hash_token(token),
        user_id=user_id,
    )
    return WantCreated(id=want_id, access_token=token, status="open")


def get_want(want_id: str, authorization: str | None, cookie_token: str | None) -> WantView:
    explicit = _want_token(authorization)
    session = None if explicit else user_from_credentials(authorization, cookie_token)
    _authorize(want_id, explicit, session)
    return _want_view(want_id)


def _buyer_ceiling(want_id: str) -> int | None:
    """Ceiling used for this want. None means the listing fallback ceiling.

    The number is passed into negotiate() and must not be logged or returned.
    """

    return repo.get_want_max(want_id)


def _ranked_matches(criteria: WantCriteria):
    ranked = []
    for match in match_listings(criteria):
        listing = repo.get_listing(match.listing_id)
        if listing is None:
            continue
        rank = 0 if listing.origin == "lister" else 1 if listing.origin == "seed" else 2
        ranked.append((rank, -match.score, match, listing))
    ranked.sort(key=lambda item: (item[0], item[1], item[3].id))
    return [(item[2], item[3]) for item in ranked]


def _remember_external(want_id: str, listing: ListingRecord, score: float, reason: str) -> None:
    ceiling = _buyer_ceiling(want_id)
    limits = repo.get_limits(listing.id)
    floor = limits.seller_min if limits is not None else None
    amount = _suggest_offer(listing.price, ceiling, floor)
    source = source_name_for(listing.origin, listing.source_url)
    message = (
        f"Hi — I saw {listing.title} on {source}. "
        f"I can offer ${amount} and pick it up in the Bay Area. Is it still available?"
    )
    message = _phrase_offer(listing, amount, source, message)
    created = repo.upsert_recommendation(want_id, listing.id, amount, message)
    repo.upsert_want_match(want_id, listing.id, score, reason, None)
    if created:
        _note(f"Buyer agent drafted a message for {listing.title} on {source}")
        _notify(
            repo.get_want_owner(want_id),
            "match",
            f"Your buyer bot found {listing.title} on {source}",
            "/bots",
        )


def _open_negotiation(want_id: str, listing: ListingRecord, score: float, reason: str) -> bool:
    if listing.origin == "scout":
        _remember_external(want_id, listing, score, reason)
        return False
    existing = next(
        (row for row in repo.list_want_matches(want_id) if row.listing_id == listing.id),
        None,
    )
    if existing is not None and existing.negotiation_id:
        repo.upsert_want_match(want_id, listing.id, score, reason, existing.negotiation_id)
        return False
    limits = repo.get_limits(listing.id)
    if limits is None:
        return False
    ceiling = _buyer_ceiling(want_id)
    if ceiling is None:
        ceiling = limits.buyer_max
    owner = repo.get_want_owner(want_id)
    item = _negotiate_and_store(
        listing,
        ceiling,
        limits.seller_min,
        want_id=want_id,
        user_id=owner,
    )
    repo.upsert_want_match(want_id, listing.id, score, reason, item.id)
    return True


def _consider_matches(want_id: str, *, finish: bool) -> int:
    record = repo.get_want(want_id)
    if record is None:
        raise APIError(404, "not_found", "Want not found.")
    criteria = WantCriteria(
        category=record.category,
        area=record.area,
        keywords=record.keywords,
    )
    ceiling = repo.get_want_max(want_id)
    opened = 0
    for match, listing in _ranked_matches(criteria):
        if ceiling is not None and listing.price > ceiling * HUNT_STRETCH:
            continue
        if listing.origin == "scout":
            _remember_external(want_id, listing, match.score, match.reason)
            continue
        if opened >= MAX_HUNT_MATCHES:
            repo.upsert_want_match(want_id, listing.id, match.score, match.reason, None)
            continue
        if _open_negotiation(want_id, listing, match.score, match.reason):
            opened += 1
        else:
            existing = next(
                (row for row in repo.list_want_matches(want_id) if row.listing_id == listing.id),
                None,
            )
            if existing is not None and existing.negotiation_id:
                opened += 1
    if opened:
        repo.set_want_status(want_id, "negotiating")
    elif finish:
        repo.set_want_status(want_id, "done")
    return opened


def execute_hunt(want_id: str) -> None:
    if repo.get_want(want_id) is None:
        raise APIError(404, "not_found", "Want not found.")
    repo.set_want_status(want_id, "hunting")
    _consider_matches(want_id, finish=True)


def execute_target(want_id: str, listing_id: str) -> None:
    if repo.get_want(want_id) is None:
        raise APIError(404, "not_found", "Want not found.")
    listing = repo.get_listing(listing_id)
    if listing is None:
        raise APIError(404, "not_found", "Listing not found.")
    repo.set_want_status(want_id, "negotiating")
    _open_negotiation(want_id, listing, score=1.0, reason="Directed at this listing.")
    repo.set_want_status(want_id, "negotiating")


def hunt_want(want_id: str, authorization: str | None, cookie_token: str | None) -> WantView:
    explicit = _want_token(authorization)
    session = None if explicit else user_from_credentials(authorization, cookie_token)
    _authorize(want_id, explicit, session)
    from backend.app.runner import run_hunt

    run_hunt(want_id)
    return _want_view(want_id)


def target_want(
    want_id: str,
    authorization: str | None,
    cookie_token: str | None,
    listing_id: str,
) -> WantView:
    explicit = _want_token(authorization)
    session = None if explicit else user_from_credentials(authorization, cookie_token)
    _authorize(want_id, explicit, session)
    from backend.app.runner import run_target

    run_target(want_id, listing_id)
    return _want_view(want_id)


def accept_negotiation(negotiation_id: str, user_id: str) -> Negotiation:
    item = repo.get_negotiation(negotiation_id)
    if item is None:
        raise APIError(404, "not_found", "Negotiation not found.")
    owner = repo.negotiation_user_id(negotiation_id)
    want_owner = repo.get_want_owner(item.want_id) if item.want_id else None
    if user_id not in {owner, want_owner}:
        raise APIError(401, "unauthorized", "Sign in to continue.")
    if item.outcome != "deal":
        raise APIError(400, "bad_request", "There is no deal to accept.")
    if not item.accepted:
        repo.set_negotiation_accepted(negotiation_id)
        listing = repo.get_listing(item.listing_id)
        title = listing.title if listing else "a listing"
        _note(f"Buyer accepted the deal on {title}")
    accepted = repo.get_negotiation(negotiation_id)
    if accepted is None:
        raise APIError(404, "not_found", "Negotiation not found.")
    return accepted


def _public_line(message: str, fallback: str) -> str:
    lowered = message.lower()
    if any(word in lowered for word in _FORBIDDEN_WORDS):
        return fallback
    for number in repo.secret_numbers():
        if str(number) in message:
            return fallback
    return message


def _notify(user_id: str | None, kind: str, message: str, href: str | None) -> None:
    if not user_id:
        return
    safe = _public_line(message, "")
    if not safe:
        return
    repo.add_notification(_new_id("ntf_"), user_id, _now_iso(), kind, safe[:240], href)


def _announce_talk(listing: ListingRecord, item: Negotiation) -> None:
    buyer = repo.negotiation_user_id(item.id)
    seller = repo.get_listing_owner(listing.id)
    if item.want_id and buyer:
        _notify(buyer, "match", f"Your buyer bot matched {listing.title}", "/bots")
        if item.outcome == "deal":
            _notify(
                buyer,
                "deal",
                f"Your buyer bot reached a deal on {listing.title}",
                f"/negotiations/{item.id}",
            )
        elif any(message.kind == "counter" for message in item.messages):
            _notify(
                buyer,
                "counteroffer",
                f"The seller countered on {listing.title}",
                f"/negotiations/{item.id}",
            )
    if seller:
        offer = next(
            (message.amount for message in item.messages if message.kind == "offer" and message.amount),
            None,
        )
        if offer is None:
            text = f"A buyer opened a talk on {listing.title}"
        else:
            text = _public_line(
                f"A buyer offered ${offer} on {listing.title}",
                f"A buyer offered on {listing.title}",
            )
        _notify(seller, "offer", text, "/bots")


def _notify_price_drop(listing: ListingRecord, new_price: int) -> None:
    text = _public_line(
        f"The price dropped to ${new_price} on {listing.title}",
        f"The price dropped on {listing.title}",
    )
    href = f"/listings/{listing.id}"
    for user_id in repo.users_watching(listing.id):
        _notify(user_id, "price_drop", text, href)
    _notify(repo.get_listing_owner(listing.id), "price_drop", text, href)


def _phrase_offer(listing: ListingRecord, amount: int, source: str, fallback: str) -> str:
    """Ask the message model to phrase a paste-ready offer. The fallback has no private limits."""

    parsed = parse_json_reply(
        complete(
            (
                "Write one short message a buyer can paste to a seller. "
                "Use only the offer amount below. Do not invent a budget, a maximum, or a minimum. "
                'Reply as JSON {"message": "..."}.\n'
                f"Title: {listing.title}\n"
                f"Source: {source}\n"
                f"Neighborhood: {listing.neighborhood}\n"
                f"Offer: {amount}"
            ),
            model=message_model(),
            effort=message_effort(),
            max_tokens=200,
        )
    )
    if not isinstance(parsed, dict) or not isinstance(parsed.get("message"), str):
        return fallback
    sentence = " ".join(parsed["message"].split())
    if not sentence or len(sentence) > 400:
        return fallback
    return _public_line(sentence, fallback)


def activity() -> ActivityResponse:
    events = [ActivityEvent(at=stamp, message=text) for stamp, text in repo.list_activity()]
    return ActivityResponse(events=events)


def search_board(q: str | None, category: str | None) -> SearchResponse:
    _require_category(category)
    text = q.strip() if q else ""
    rows = repo.list_listings(category, text or None, None)
    if text and rows:
        return SearchResponse(listings=[_card(row) for row in rows[:8]], scouted=False)
    if not text:
        return SearchResponse(listings=[_card(row) for row in rows[:8]], scouted=False)
    parsed = parse_want(text)
    chosen = category or parsed.category
    _require_category(chosen)
    added = 0
    try:
        found = scout_query(text, chosen)
        added = _ingest_scouted(list(found))
    except ScoutStopped as exc:
        _note(f"Scout stopped: {exc.reason}. {exc.message}")
    except Exception:
        log.exception("search scout failed")
    if added == 0:
        categories = [chosen] if chosen else list(CATEGORIES)
        try:
            outcome = run_scout(categories)
            added = outcome.added
        except Exception:
            log.exception("search scout failed")
    rows = repo.list_listings(category, text or None, None)
    if not rows and parsed.keywords:
        for word in parsed.keywords:
            rows = repo.list_listings(chosen, word, None)
            if rows:
                break
    if not rows and added:
        rows = repo.list_listings(chosen, None, None)
    return SearchResponse(listings=[_card(row) for row in rows[:8]], scouted=True)


def my_bots(user_id: str) -> BotsResponse:
    buyers: list[BuyerBot] = []
    for want_id in repo.list_want_ids_for_user(user_id):
        view = _want_view(want_id)
        buyers.append(
            BuyerBot(
                id=view.id,
                text=view.text,
                status=view.status,
                matches=view.matches,
                negotiations=view.negotiations,
                recommendations=view.recommendations,
            )
        )
    sellers: list[SellerBot] = []
    for listing_id in repo.list_listing_ids_for_user(user_id):
        listing = repo.get_listing(listing_id)
        if listing is None:
            continue
        sellers.append(
            SellerBot(
                listing_id=listing.id,
                title=listing.title,
                price=listing.price,
                negotiations=repo.list_negotiations_for_listing(listing.id),
            )
        )
    return BotsResponse(buyers=buyers, sellers=sellers)


def notifications_for(user_id: str) -> NotificationsResponse:
    rows = repo.list_notifications(user_id)
    return NotificationsResponse(
        unread=repo.unread_count(user_id),
        notifications=[
            NotificationPublic(
                id=row.id,
                at=row.created_at,
                kind=row.kind,
                message=row.message,
                href=row.href,
                unread=row.unread,
            )
            for row in rows
        ],
    )


def mark_read(user_id: str, ids: list[str] | None) -> NotificationsResponse:
    repo.mark_notifications_read(user_id, ids, _now_iso())
    return notifications_for(user_id)


_last_scout_at = 0.0


def _scout_interval_s() -> int:
    raw = os.environ.get("SCOUT_INTERVAL_S", "600").strip() or "600"
    try:
        seconds = int(raw)
    except ValueError:
        seconds = 600
    return max(30, seconds)


def run_background_tick() -> None:
    """Scout on a slow cycle, then rematch and negotiate. Never raises."""

    global _last_scout_at
    now = time.time()
    thin = repo.count_origin("scout") < 1
    due = _last_scout_at == 0.0 or (now - _last_scout_at) >= _scout_interval_s()
    if due or thin and _last_scout_at == 0.0:
        _last_scout_at = now
        try:
            run_scout(list(CATEGORIES))
        except Exception:
            log.exception("background scout failed")
    try:
        for want in repo.list_active_wants():
            try:
                _consider_matches(want.id, finish=False)
            except Exception:
                log.exception("background rematch failed")
    except Exception:
        log.exception("background want scan failed")
