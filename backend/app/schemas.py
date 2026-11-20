"""Frozen API shapes. Field names and enums live here and nowhere else on the server.

The public want view has no private max and no access token. The token is returned
once, from POST /api/wants. Mirror these shapes in the frontend client (Person A)
and in docs/INTEGRATION.md.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["bikes", "computers", "furniture"]
Origin = Literal["seed", "scout", "lister"]
Verdict = Literal["good_deal", "fair", "overpriced"]
TrustLevel = Literal["high", "medium", "low"]
NegotiationStatus = Literal["closed"]
Outcome = Literal["deal", "no_deal"]
MessageFrom = Literal["buyer", "seller"]
MessageKind = Literal["offer", "counter", "accept", "decline"]
ScoutReason = Literal["captcha", "blocked", "other"]
ErrorCode = Literal["not_found", "bad_request", "unauthorized", "scout_stopped"]
WantStatus = Literal["open", "hunting", "negotiating", "done"]

CATEGORIES: tuple[Category, ...] = ("bikes", "computers", "furniture")


class Comp(BaseModel):
    title: str
    price: int
    url: str


class AppraisalSummary(BaseModel):
    estimated_value: int
    verdict: Verdict


class Appraisal(AppraisalSummary):
    low: int
    high: int
    comps: list[Comp]


class InspectionSummary(BaseModel):
    trust_level: TrustLevel


class Signal(BaseModel):
    code: str
    reason: str


class Inspection(InspectionSummary):
    signals: list[Signal]


class ListingCard(BaseModel):
    id: str
    category: Category
    title: str
    price: int
    photos: list[str]
    neighborhood: str
    posted_at: str
    origin: Origin
    source_name: str
    appraisal: AppraisalSummary
    inspection: InspectionSummary
    sold_for: int | None = None


class Outreach(BaseModel):
    amount: int
    message: str


class ListingDetail(ListingCard):
    description: str
    source_url: str | None
    appraisal: Appraisal
    inspection: Inspection
    outreach: Outreach | None = None


class ListingListResponse(BaseModel):
    listings: list[ListingCard]


class Draft(BaseModel):
    category: Category
    title: str
    description: str
    suggested_price: int


class ListerResponse(BaseModel):
    draft: Draft


class PublishListingRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: Category
    title: str
    description: str
    price: int = Field(ge=0)
    photos: list[str] = Field(min_length=1)
    neighborhood: str = Field(min_length=1)
    # Stored server-side for the seller agent. Never copied onto a response.
    minimum: int | None = Field(default=None, ge=0)


class NegotiationMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: MessageFrom = Field(alias="from", serialization_alias="from")
    kind: MessageKind
    amount: int | None
    text: str
    at: str


class Negotiation(BaseModel):
    id: str
    listing_id: str
    want_id: str | None = None
    status: NegotiationStatus
    outcome: Outcome
    accepted: bool = False
    messages: list[NegotiationMessage]


class StartNegotiationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    listing_id: str


class ScoutReport(BaseModel):
    reason: ScoutReason
    message: str


class ScoutRunRequest(BaseModel):
    categories: list[Category] = Field(default_factory=lambda: list(CATEGORIES), min_length=1)


class ScoutRunResponse(BaseModel):
    added: int
    cached: int
    stopped: bool
    report: ScoutReport | None


class WantCreateRequest(BaseModel):
    """Creator-supplied fields. The private max is stored and never serialized back."""

    model_config = ConfigDict(extra="ignore")

    text: str = Field(min_length=1)
    category: Category | None = None
    area: str | None = None
    max_price: int | None = Field(default=None, ge=0)


class WantCreated(BaseModel):
    id: str
    access_token: str
    status: WantStatus


class WantCriteriaPublic(BaseModel):
    category: Category | None
    area: str | None
    keywords: list[str]


class WantMatchPublic(BaseModel):
    listing_id: str
    score: float
    reason: str
    title: str
    price: int
    origin: Origin
    source_name: str
    source_url: str | None = None
    appraisal: AppraisalSummary
    inspection: InspectionSummary


class RecommendationPublic(BaseModel):
    listing_id: str
    title: str
    source_name: str
    source_url: str | None
    suggested_offer: int
    message: str


class WantView(BaseModel):
    id: str
    text: str
    criteria: WantCriteriaPublic
    status: WantStatus
    matches: list[WantMatchPublic]
    negotiations: list[Negotiation]
    recommendations: list[RecommendationPublic] = Field(default_factory=list)


class AuthRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=8, max_length=200)


class UserPublic(BaseModel):
    id: str
    email: str


class ActivityEvent(BaseModel):
    at: str
    message: str


class ActivityResponse(BaseModel):
    events: list[ActivityEvent]


class WantTargetRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    listing_id: str


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    q: str = ""
    category: Category | None = None


class SearchResponse(BaseModel):
    listings: list[ListingCard]
    scouted: bool


class BuyerBot(BaseModel):
    id: str
    text: str
    status: WantStatus
    matches: list[WantMatchPublic]
    negotiations: list[Negotiation]
    recommendations: list[RecommendationPublic]


class SellerBot(BaseModel):
    listing_id: str
    title: str
    price: int
    negotiations: list[Negotiation]


class BotsResponse(BaseModel):
    buyers: list[BuyerBot]
    sellers: list[SellerBot]


class NotificationPublic(BaseModel):
    id: str
    at: str
    kind: str
    message: str
    href: str | None
    unread: bool


class NotificationsResponse(BaseModel):
    unread: int
    notifications: list[NotificationPublic]


class MarkReadRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ids: list[str] | None = None


class OpenThreadRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    listing_id: str
    intent: Literal["offer", "message", "bot"]
    text: str | None = None
    amount: int | None = Field(default=None, ge=0)
    limit: int | None = Field(default=None, ge=0)


class ThreadMessageRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = ""
    amount: int | None = Field(default=None, ge=0)
    kind: Literal["text", "offer", "counter", "accept", "decline"] = "text"


class ThreadModeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: Literal["manual", "bot"]


class ThreadLimitRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    limit: int = Field(ge=0)


class ThreadMessagePublic(BaseModel):
    at: str
    author: Literal["buyer", "buyer_bot", "seller", "seller_bot"]
    kind: Literal["text", "offer", "counter", "accept", "decline"]
    amount: int | None
    text: str


class ThreadView(BaseModel):
    id: str
    listing_id: str
    listing_title: str
    listing_price: int
    origin: Origin
    role: Literal["buyer", "seller"]
    want_id: str | None = None
    want_label: str | None = None
    buyer_mode: Literal["manual", "bot"]
    seller_mode: Literal["manual", "bot"]
    status: Literal["open", "deal", "declined"]
    summary: str
    messages: list[ThreadMessagePublic]
    my_limit: int | None = None


class ThreadSummary(BaseModel):
    id: str
    listing_id: str
    title: str
    summary: str
    updated_at: str


class BuyerBotInbox(BaseModel):
    id: str
    label: str
    threads: list[ThreadSummary]


class ListingInbox(BaseModel):
    listing_id: str
    title: str
    threads: list[ThreadSummary]


class DealsResponse(BaseModel):
    buyer_bots: list[BuyerBotInbox]
    direct: list[ThreadSummary]
    listings: list[ListingInbox]


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
