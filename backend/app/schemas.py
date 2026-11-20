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
    appraisal: AppraisalSummary
    inspection: InspectionSummary


class ListingDetail(ListingCard):
    description: str
    source_url: str | None
    appraisal: Appraisal
    inspection: Inspection


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
    # Lowest price the seller will take. Stored server-side, never returned.
    min_price: int | None = Field(default=None, ge=0)


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
    appraisal: AppraisalSummary
    inspection: InspectionSummary


class WantView(BaseModel):
    id: str
    text: str
    criteria: WantCriteriaPublic
    status: WantStatus
    matches: list[WantMatchPublic]
    negotiations: list[Negotiation]


class WantTargetRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    listing_id: str


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody
