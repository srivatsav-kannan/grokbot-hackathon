"""HTTP contract. Handlers stay thin and call backend.app.services.

Person C (@heruirayli) owns this file.
"""

from typing import Annotated

from fastapi import APIRouter, File, Header, UploadFile

from backend.app.errors import APIError

from backend.app import services
from backend.app.schemas import (
    ListerResponse,
    ListingDetail,
    ListingListResponse,
    Negotiation,
    PublishListingRequest,
    ScoutRunRequest,
    ScoutRunResponse,
    StartNegotiationRequest,
    WantCreateRequest,
    WantCreated,
    WantTargetRequest,
    WantView,
)

router = APIRouter()


@router.get("/health")
def get_health() -> dict[str, bool]:
    return {"ok": True}


def _bearer(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization:
        raise APIError(401, "unauthorized", "Want token required.")
    scheme, _, rest = authorization.partition(" ")
    token = rest.strip()
    if scheme.lower() != "bearer" or not token:
        raise APIError(401, "unauthorized", "Want token required.")
    return token


@router.get("/listings", response_model=ListingListResponse)
def get_listings(category: str | None = None, q: str | None = None) -> ListingListResponse:
    return services.list_listings(category, q)


@router.get("/listings/{listing_id}", response_model=ListingDetail)
def get_listing(listing_id: str) -> ListingDetail:
    return services.get_listing(listing_id)


@router.post("/lister", response_model=ListerResponse)
async def post_lister(photo: UploadFile = File(...)) -> ListerResponse:
    payload = await photo.read()
    return services.create_draft(payload, photo.filename)


@router.post("/listings", response_model=ListingDetail, status_code=201)
def post_listing(body: PublishListingRequest) -> ListingDetail:
    return services.publish_listing(body)


@router.post("/negotiations", response_model=Negotiation, status_code=201)
def post_negotiation(body: StartNegotiationRequest) -> Negotiation:
    return services.start_negotiation(body.listing_id)


@router.get("/negotiations/{negotiation_id}", response_model=Negotiation)
def get_negotiation(negotiation_id: str) -> Negotiation:
    return services.get_negotiation(negotiation_id)


@router.post("/scout/run", response_model=ScoutRunResponse)
def post_scout(body: ScoutRunRequest) -> ScoutRunResponse:
    return services.run_scout(list(body.categories))


@router.post("/wants", response_model=WantCreated, status_code=201)
def post_want(body: WantCreateRequest) -> WantCreated:
    return services.create_want(body.text, body.category, body.area, body.max_price)


@router.get("/wants/{want_id}", response_model=WantView)
def get_want(want_id: str, authorization: Annotated[str | None, Header()] = None) -> WantView:
    return services.get_want(want_id, _bearer(authorization))


@router.post("/wants/{want_id}/hunt", response_model=WantView)
def post_hunt(want_id: str, authorization: Annotated[str | None, Header()] = None) -> WantView:
    return services.hunt_want(want_id, _bearer(authorization))


@router.post("/wants/{want_id}/target", response_model=WantView)
def post_target(
    want_id: str,
    body: WantTargetRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> WantView:
    return services.target_want(want_id, _bearer(authorization), body.listing_id)
