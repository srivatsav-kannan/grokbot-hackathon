"""Routes call these functions. Agents and the database stay behind them.

Person C (@heruirayli) owns this file. Call the agent functions; do not rewrite
their decisions here. Private ceilings and token hashes stay inside this module
and the repository. They are not fields on the objects returned below.
"""

from __future__ import annotations

import hashlib
import secrets

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
from backend.app.agents.negotiator import negotiate
from backend.app.agents.scout import ScoutStopped, scout_run
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
    WantCreated,
    WantCriteriaPublic,
    WantMatchPublic,
    WantView,
)


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return prefix + secrets.token_hex(4)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def limits_for_asking_price(price: int) -> Limits:
    """Server-side policy for a listing a person just published. Not returned.

    The numbers are a seller floor and a fallback buyer ceiling for the
    on-site negotiate endpoint. A want uses its own stored ceiling instead.
    """

    seller_min = max(1, int(round(price * 0.75)))
    buyer_max = max(seller_min, int(round(price * 0.95)))
    return Limits(buyer_max=buyer_max, seller_min=seller_min)


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
        description=listing.description,
        source_url=listing.source_url,
        appraisal=appraisal,
        inspection=inspection,
    )


def list_listings(category: str | None, q: str | None) -> ListingListResponse:
    _require_category(category)
    text = q.strip() if q else None
    rows = repo.list_listings(category, text or None)
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


def publish_listing(body: PublishListingRequest) -> ListingDetail:
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
    repo.insert_listing(listing, appraisal, inspection, limits_for_asking_price(body.price))
    return _detail(listing)


def _negotiate_and_store(
    listing: ListingRecord,
    buyer_max: int,
    seller_min: int,
    want_id: str | None = None,
) -> Negotiation:
    draft = negotiate(listing, buyer_max, seller_min)
    item = Negotiation(
        id=_new_id("neg_"),
        listing_id=listing.id,
        want_id=want_id,
        status="closed",
        outcome=draft.outcome,
        messages=draft.messages,
    )
    repo.insert_negotiation(item)
    return item


def start_negotiation(listing_id: str) -> Negotiation:
    """On-site offer. Uses the listing's stored ceiling, not a client-supplied one."""

    listing = repo.get_listing(listing_id)
    if listing is None:
        raise APIError(404, "not_found", "Listing not found.")
    limits = repo.get_limits(listing_id)
    if limits is None:
        raise APIError(404, "not_found", "Negotiation is not available for this listing.")
    return _negotiate_and_store(listing, limits.buyer_max, limits.seller_min)


def get_negotiation(negotiation_id: str) -> Negotiation:
    item = repo.get_negotiation(negotiation_id)
    if item is None:
        raise APIError(404, "not_found", "Negotiation not found.")
    return item


def run_scout(categories: list[str]) -> ScoutRunResponse:
    for category in categories:
        _require_category(category)
    try:
        result = scout_run(categories)
    except ScoutStopped as exc:
        return ScoutRunResponse(
            added=0,
            cached=repo.count_listings(),
            stopped=True,
            report=ScoutReport(reason=exc.reason, message=exc.message),  # type: ignore[arg-type]
        )
    added = 0
    for listing in result.listings:
        # Scout ids come from the source URL, so a listing already stored is skipped.
        if repo.get_listing(listing.id) is not None:
            continue
        # Appraise and inspect first. insert_listing writes the listing, appraisal,
        # inspection, and limits in one transaction, so GET /api/listings never sees
        # a scouted row without its badges.
        appraisal = appraise(listing)
        inspection = inspect(listing, appraisal)
        repo.insert_listing(listing, appraisal, inspection, limits_for_asking_price(listing.price))
        added += 1
    return ScoutRunResponse(
        added=added,
        cached=repo.count_listings(),
        stopped=result.stopped,
        report=result.report,
    )


def _authorize(want_id: str, token: str) -> None:
    if repo.get_want(want_id) is None:
        raise APIError(404, "not_found", "Want not found.")
    digest = repo.get_token_hash(want_id)
    if not token or digest is None or not secrets.compare_digest(digest, _hash_token(token)):
        raise APIError(401, "unauthorized", "Want token required.")


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
                appraisal=AppraisalSummary(
                    estimated_value=appraisal.estimated_value,
                    verdict=appraisal.verdict,
                ),
                inspection=InspectionSummary(trust_level=inspection.trust_level),
            )
        )
    return WantView(
        id=record.id,
        text=record.text,
        criteria=_criteria_public(record),
        status=record.status,  # type: ignore[arg-type]
        matches=matches,
        negotiations=repo.list_negotiations_for_want(want_id),
    )


def create_want(
    text: str,
    category: str | None,
    area: str | None,
    max_price: int | None,
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
    )
    return WantCreated(id=want_id, access_token=token, status="open")


def get_want(want_id: str, token: str) -> WantView:
    _authorize(want_id, token)
    return _want_view(want_id)


def _buyer_ceiling(want_id: str) -> int | None:
    """Ceiling used for this want. None means the listing fallback ceiling.

    The number is passed into negotiate() and must not be logged or returned.
    """

    return repo.get_want_max(want_id)


def _open_negotiation(want_id: str, listing: ListingRecord, score: float, reason: str) -> None:
    existing = next(
        (row for row in repo.list_want_matches(want_id) if row.listing_id == listing.id),
        None,
    )
    if existing is not None and existing.negotiation_id:
        repo.upsert_want_match(want_id, listing.id, score, reason, existing.negotiation_id)
        return
    limits = repo.get_limits(listing.id)
    if limits is None:
        return
    ceiling = _buyer_ceiling(want_id)
    if ceiling is None:
        ceiling = limits.buyer_max
    item = _negotiate_and_store(listing, ceiling, limits.seller_min, want_id=want_id)
    repo.upsert_want_match(want_id, listing.id, score, reason, item.id)


def execute_hunt(want_id: str) -> None:
    record = repo.get_want(want_id)
    if record is None:
        raise APIError(404, "not_found", "Want not found.")
    repo.set_want_status(want_id, "hunting")
    criteria = WantCriteria(
        category=record.category,
        area=record.area,
        keywords=record.keywords,
    )
    ceiling = repo.get_want_max(want_id)
    opened = 0
    for match in match_listings(criteria):
        listing = repo.get_listing(match.listing_id)
        if listing is None:
            continue
        if ceiling is not None and listing.price > ceiling:
            continue
        repo.set_want_status(want_id, "negotiating")
        _open_negotiation(want_id, listing, match.score, match.reason)
        opened += 1
        if opened >= MAX_HUNT_MATCHES:
            break
    repo.set_want_status(want_id, "negotiating" if opened else "done")


def execute_target(want_id: str, listing_id: str) -> None:
    if repo.get_want(want_id) is None:
        raise APIError(404, "not_found", "Want not found.")
    listing = repo.get_listing(listing_id)
    if listing is None:
        raise APIError(404, "not_found", "Listing not found.")
    repo.set_want_status(want_id, "negotiating")
    _open_negotiation(want_id, listing, score=1.0, reason="Directed at this listing.")
    repo.set_want_status(want_id, "negotiating")


def hunt_want(want_id: str, token: str) -> WantView:
    _authorize(want_id, token)
    from backend.app.runner import run_hunt

    run_hunt(want_id)
    return _want_view(want_id)


def target_want(want_id: str, token: str, listing_id: str) -> WantView:
    _authorize(want_id, token)
    from backend.app.runner import run_target

    run_target(want_id, listing_id)
    return _want_view(want_id)
