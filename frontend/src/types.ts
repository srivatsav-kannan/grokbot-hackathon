/** Public API shapes. Field names match backend/app/schemas.py. Do not add fields. */

export type Category = "bikes" | "computers" | "furniture";
export type Origin = "seed" | "scout" | "lister";
export type Verdict = "good_deal" | "fair" | "overpriced";
export type TrustLevel = "high" | "medium" | "low";
export type Outcome = "deal" | "no_deal";
export type MessageFrom = "buyer" | "seller";
export type MessageKind = "offer" | "counter" | "accept" | "decline";
export type WantStatus = "open" | "hunting" | "negotiating" | "done";
export type ErrorCode = "not_found" | "bad_request" | "unauthorized" | "scout_stopped";

export interface AppraisalSummary {
  estimated_value: number;
  verdict: Verdict;
}

export interface Comp {
  title: string;
  price: number;
  url: string;
}

export interface Appraisal extends AppraisalSummary {
  low: number;
  high: number;
  comps: Comp[];
}

export interface InspectionSummary {
  trust_level: TrustLevel;
}

export interface Signal {
  code: string;
  reason: string;
}

export interface Inspection extends InspectionSummary {
  signals: Signal[];
}

export interface ListingCard {
  id: string;
  category: Category;
  title: string;
  price: number;
  photos: string[];
  neighborhood: string;
  posted_at: string;
  origin: Origin;
  source_name: string;
  appraisal: AppraisalSummary;
  inspection: InspectionSummary;
}

export interface Outreach {
  amount: number;
  message: string;
}

export interface ListingDetail extends Omit<ListingCard, "appraisal" | "inspection"> {
  description: string;
  source_url: string | null;
  appraisal: Appraisal;
  inspection: Inspection;
  outreach?: Outreach | null;
}

export interface ListingListResponse {
  listings: ListingCard[];
}

export interface Draft {
  category: Category;
  title: string;
  description: string;
  suggested_price: number;
}

export interface ListerResponse {
  draft: Draft;
}

export interface PublishListingRequest {
  category: Category;
  title: string;
  description: string;
  price: number;
  photos: string[];
  neighborhood: string;
  minimum?: number;
}

export interface NegotiationMessage {
  from: MessageFrom;
  kind: MessageKind;
  amount: number | null;
  text: string;
  at: string;
}

export interface Negotiation {
  id: string;
  listing_id: string;
  want_id: string | null;
  status: "closed";
  outcome: Outcome;
  accepted: boolean;
  messages: NegotiationMessage[];
}

export interface WantCreated {
  id: string;
  access_token: string;
  status: WantStatus;
}

export interface WantCriteriaPublic {
  category: Category | null;
  area: string | null;
  keywords: string[];
}

export interface WantMatchPublic {
  listing_id: string;
  score: number;
  reason: string;
  title: string;
  price: number;
  origin: Origin;
  source_name: string;
  source_url: string | null;
  appraisal: AppraisalSummary;
  inspection: InspectionSummary;
}

export interface RecommendationPublic {
  listing_id: string;
  title: string;
  source_name: string;
  source_url: string | null;
  suggested_offer: number;
  message: string;
}

export interface WantView {
  id: string;
  text: string;
  criteria: WantCriteriaPublic;
  status: WantStatus;
  matches: WantMatchPublic[];
  negotiations: Negotiation[];
  recommendations: RecommendationPublic[];
}

export interface UserPublic {
  id: string;
  email: string;
}

export interface SearchResponse {
  listings: ListingCard[];
  scouted: boolean;
}

export interface BuyerBot {
  id: string;
  text: string;
  status: WantStatus;
  matches: WantMatchPublic[];
  negotiations: Negotiation[];
  recommendations: RecommendationPublic[];
}

export interface SellerBot {
  listing_id: string;
  title: string;
  price: number;
  negotiations: Negotiation[];
}

export interface BotsResponse {
  buyers: BuyerBot[];
  sellers: SellerBot[];
}

export interface NotificationItem {
  id: string;
  at: string;
  kind: string;
  message: string;
  href: string | null;
  unread: boolean;
}

export interface NotificationsResponse {
  unread: number;
  notifications: NotificationItem[];
}

export interface ErrorBody {
  code: ErrorCode | string;
  message: string;
}

export interface ErrorResponse {
  error: ErrorBody;
}

export type SortKey = "newest" | "price_asc" | "price_desc";

export type ThreadAuthor = "buyer" | "buyer_bot" | "seller" | "seller_bot";

export interface ThreadMessage {
  at: string;
  author: ThreadAuthor;
  kind: string;
  amount: number | null;
  text: string;
}

export interface ThreadView {
  id: string;
  listing_id: string;
  listing_title: string;
  listing_price: number;
  origin: Origin;
  role: "buyer" | "seller";
  want_id: string | null;
  want_label: string | null;
  buyer_mode: "manual" | "bot";
  seller_mode: "manual" | "bot";
  status: "open" | "deal" | "declined";
  summary: string;
  messages: ThreadMessage[];
  my_limit: number | null;
}

export interface ThreadSummary {
  id: string;
  listing_id: string;
  title: string;
  summary: string;
  updated_at: string;
}

export interface DealsResponse {
  buyer_bots: { id: string; label: string; threads: ThreadSummary[] }[];
  direct: ThreadSummary[];
  listings: { listing_id: string; title: string; threads: ThreadSummary[] }[];
}
