"""HTTP contract. Handlers stay thin and call backend.app.services.

Person C (@heruirayli) owns this file.
"""

from typing import Annotated

from fastapi import APIRouter, File, Header, Request, Response, UploadFile

from backend.app import deals, services
from backend.app.schemas import (
    ActivityResponse,
    AuthRequest,
    BotsResponse,
    MarkReadRequest,
    NotificationsResponse,
    SearchRequest,
    SearchResponse,
    ListerResponse,
    ListingDetail,
    ListingListResponse,
    Negotiation,
    PublishListingRequest,
    ScoutRunRequest,
    ScoutRunResponse,
    DealsResponse,
    OpenThreadRequest,
    StartNegotiationRequest,
    ThreadLimitRequest,
    ThreadMessageRequest,
    ThreadModeRequest,
    ThreadView,
    UserPublic,
    WantCreateRequest,
    WantCreated,
    WantTargetRequest,
    WantView,
)

router = APIRouter()


def _cookie(request: Request) -> str | None:
    return request.cookies.get(services.SESSION_COOKIE)


def _cookie_secure(request: Request) -> bool:
    """Render terminates TLS and forwards https. Local HTTP must stay insecure."""

    forwarded = request.headers.get("x-forwarded-proto", "")
    if any(part.strip().lower() == "https" for part in forwarded.split(",")):
        return True
    host = (request.headers.get("host") or request.url.hostname or "").lower()
    if host.endswith(".onrender.com"):
        return True
    return request.url.scheme == "https"


def _set_session(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        services.SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(request),
        max_age=60 * 60 * 24 * 30,
        path="/",
    )


def _clear_session(response: Response, request: Request) -> None:
    response.delete_cookie(
        services.SESSION_COOKIE,
        path="/",
        samesite="lax",
        secure=_cookie_secure(request),
    )


def _user(request: Request, authorization: str | None):
    return services.require_user(authorization, _cookie(request))


@router.get("/health")
def get_health() -> dict[str, bool | str]:
    from backend.app.db import using_postgres

    return {"ok": True, "database": "postgres" if using_postgres() else "sqlite"}


@router.post("/auth/signup", response_model=UserPublic, status_code=201)
def post_signup(body: AuthRequest, request: Request, response: Response) -> UserPublic:
    user, token = services.signup(body.email, body.password)
    _set_session(response, request, token)
    return user


@router.post("/auth/login", response_model=UserPublic)
def post_login(body: AuthRequest, request: Request, response: Response) -> UserPublic:
    user, token = services.login(body.email, body.password)
    _set_session(response, request, token)
    return user


@router.post("/auth/logout", status_code=204)
def post_logout(
    request: Request,
    response: Response,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    services.logout(authorization, _cookie(request))
    _clear_session(response, request)
    response.status_code = 204
    return response


@router.get("/auth/me", response_model=UserPublic)
def get_me(request: Request, authorization: Annotated[str | None, Header()] = None) -> UserPublic:
    return services.current_user(authorization, _cookie(request))


@router.get("/activity", response_model=ActivityResponse)
def get_activity() -> ActivityResponse:
    return services.activity()


@router.post("/search", response_model=SearchResponse)
def post_search(body: SearchRequest) -> SearchResponse:
    return services.search_board(body.q, body.category)


@router.get("/bots", response_model=BotsResponse)
def get_bots(request: Request, authorization: Annotated[str | None, Header()] = None) -> BotsResponse:
    user = _user(request, authorization)
    return services.my_bots(user.id)


@router.get("/notifications", response_model=NotificationsResponse)
def get_notifications(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> NotificationsResponse:
    user = _user(request, authorization)
    return services.notifications_for(user.id)


@router.post("/notifications/read", response_model=NotificationsResponse)
def post_notifications_read(
    body: MarkReadRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> NotificationsResponse:
    user = _user(request, authorization)
    return services.mark_read(user.id, body.ids)


@router.get("/listings", response_model=ListingListResponse)
def get_listings(
    category: str | None = None,
    q: str | None = None,
    kind: str | None = None,
) -> ListingListResponse:
    return services.list_listings(category, q, kind)


@router.get("/listings/{listing_id}", response_model=ListingDetail)
def get_listing(
    listing_id: str,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> ListingDetail:
    viewer = services.user_from_credentials(authorization, _cookie(request))
    return services.get_listing(listing_id, viewer.id if viewer else None)


@router.post("/lister", response_model=ListerResponse)
async def post_lister(photo: UploadFile = File(...)) -> ListerResponse:
    payload = await photo.read()
    return services.create_draft(payload, photo.filename)


@router.post("/listings", response_model=ListingDetail, status_code=201)
def post_listing(
    body: PublishListingRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> ListingDetail:
    user = _user(request, authorization)
    return services.publish_listing(body, user.id, request.headers.get("idempotency-key"))


@router.post("/negotiations", response_model=Negotiation, status_code=201)
def post_negotiation(
    body: StartNegotiationRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> Negotiation:
    user = _user(request, authorization)
    return services.start_negotiation(body.listing_id, user.id)


@router.get("/negotiations/{negotiation_id}", response_model=Negotiation)
def get_negotiation(negotiation_id: str) -> Negotiation:
    return services.get_negotiation(negotiation_id)


@router.post("/negotiations/{negotiation_id}/accept", response_model=Negotiation)
def post_accept(
    negotiation_id: str,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> Negotiation:
    user = _user(request, authorization)
    return services.accept_negotiation(negotiation_id, user.id)


@router.post("/scout/run", response_model=ScoutRunResponse)
def post_scout(body: ScoutRunRequest) -> ScoutRunResponse:
    return services.run_scout(list(body.categories))


@router.post("/wants", response_model=WantCreated, status_code=201)
def post_want(
    body: WantCreateRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> WantCreated:
    user = _user(request, authorization)
    return services.create_want(body.text, body.category, body.area, body.max_price, user.id)


@router.get("/wants/{want_id}", response_model=WantView)
def get_want(
    want_id: str,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> WantView:
    return services.get_want(want_id, authorization, _cookie(request))


@router.post("/wants/{want_id}/hunt", response_model=WantView)
def post_hunt(
    want_id: str,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> WantView:
    return services.hunt_want(want_id, authorization, _cookie(request))


@router.post("/wants/{want_id}/target", response_model=WantView)
def post_target(
    want_id: str,
    body: WantTargetRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> WantView:
    return services.target_want(want_id, authorization, _cookie(request), body.listing_id)


@router.get("/deals", response_model=DealsResponse)
def get_deals(request: Request, authorization: Annotated[str | None, Header()] = None) -> DealsResponse:
    user = _user(request, authorization)
    return deals.inbox(user.id)


@router.post("/threads", response_model=ThreadView, status_code=201)
def post_thread(
    body: OpenThreadRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> ThreadView:
    user = _user(request, authorization)
    return deals.open_thread(
        user.id,
        body.listing_id,
        body.intent,
        body.text,
        body.amount,
        body.limit,
        request.headers.get("idempotency-key"),
    )


@router.get("/threads/{thread_id}", response_model=ThreadView)
def get_thread(
    thread_id: str,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> ThreadView:
    user = _user(request, authorization)
    return deals.thread_for(user.id, thread_id)


@router.post("/threads/{thread_id}/messages", response_model=ThreadView)
def post_thread_message(
    thread_id: str,
    body: ThreadMessageRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> ThreadView:
    user = _user(request, authorization)
    return deals.post_message(
        user.id,
        thread_id,
        body.text,
        body.amount,
        body.kind,
        request.headers.get("idempotency-key"),
    )


@router.post("/threads/{thread_id}/mode", response_model=ThreadView)
def post_thread_mode(
    thread_id: str,
    body: ThreadModeRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> ThreadView:
    user = _user(request, authorization)
    return deals.set_mode(user.id, thread_id, body.mode)


@router.post("/threads/{thread_id}/limit", response_model=ThreadView)
def post_thread_limit(
    thread_id: str,
    body: ThreadLimitRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> ThreadView:
    user = _user(request, authorization)
    return deals.set_limit(user.id, thread_id, body.limit)
