import type {
  BotsResponse,
  Category,
  ErrorResponse,
  ListerResponse,
  ListingDetail,
  ListingListResponse,
  Negotiation,
  NotificationsResponse,
  PublishListingRequest,
  DealsResponse,
  SearchResponse,
  ThreadView,
  UserPublic,
  WantCreated,
  WantView,
} from "../types";

/**
 * Price ceilings and seller floors stay on the server.
 * This module never sends buyer_max, seller_min, price_limits, or max_price.
 * The want access token is passed only as an Authorization header and is never rendered.
 */

function apiRoot(): string {
  const raw = import.meta.env.VITE_API_BASE_URL ?? "";
  return raw.replace(/\/+$/, "");
}

export function apiUrl(path: string): string {
  if (/^https?:\/\//.test(path) || path.startsWith("data:") || path.startsWith("blob:")) {
    return path;
  }
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${apiRoot()}${normalized}`;
}

export function mediaUrl(src: string): string {
  return apiUrl(src);
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(apiUrl(path), { ...init, headers, credentials: "include" });
  } catch (err) {
    if (isAbort(err)) throw err;
    throw new ApiError("unreachable", "The board didn't respond.", 0);
  }

  if (!response.ok) {
    let code = "bad_request";
    let message = "The request didn't go through.";
    try {
      const payload = (await response.json()) as Partial<ErrorResponse>;
      if (payload.error?.code) code = payload.error.code;
      if (payload.error?.message) message = payload.error.message;
    } catch {
      /* The server sometimes replies without JSON. */
    }
    throw new ApiError(code, message, response.status);
  }

  return (await response.json()) as T;
}

export interface ListingsQuery {
  category?: Category | null;
  q?: string | null;
  signal?: AbortSignal;
}

export async function listListings(query: ListingsQuery = {}): Promise<ListingListResponse> {
  const params = new URLSearchParams();
  if (query.category) params.set("category", query.category);
  const text = query.q?.trim();
  if (text) params.set("q", text);
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return request<ListingListResponse>(`/api/listings${suffix}`, { signal: query.signal });
}

export function getListing(id: string, signal?: AbortSignal): Promise<ListingDetail> {
  return request<ListingDetail>(`/api/listings/${encodeURIComponent(id)}`, { signal });
}

export function createDraft(photo: File, signal?: AbortSignal): Promise<ListerResponse> {
  const body = new FormData();
  body.append("photo", photo, photo.name);
  return request<ListerResponse>("/api/lister", { method: "POST", body, signal });
}

export function publishListing(body: PublishListingRequest): Promise<ListingDetail> {
  const payload: PublishListingRequest = {
    category: body.category,
    title: body.title,
    description: body.description,
    price: body.price,
    photos: body.photos,
    neighborhood: body.neighborhood,
  };
  if (body.minimum != null) payload.minimum = body.minimum;
  return request<ListingDetail>("/api/listings", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function startNegotiation(listingId: string): Promise<Negotiation> {
  return request<Negotiation>("/api/negotiations", {
    method: "POST",
    body: JSON.stringify({ listing_id: listingId }),
  });
}

export function getNegotiation(id: string, signal?: AbortSignal): Promise<Negotiation> {
  return request<Negotiation>(`/api/negotiations/${encodeURIComponent(id)}`, { signal });
}

export interface WantCreateInput {
  text: string;
  category?: Category | null;
  area?: string | null;
}

export function createWant(input: WantCreateInput): Promise<WantCreated> {
  const payload: { text: string; category?: Category; area?: string } = {
    text: input.text,
  };
  if (input.category) payload.category = input.category;
  if (input.area?.trim()) payload.area = input.area.trim();
  return request<WantCreated>("/api/wants", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

function wantPath(id: string, suffix = ""): string {
  return `/api/wants/${encodeURIComponent(id)}${suffix}`;
}

function bearer(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

export function getWant(id: string, token: string, signal?: AbortSignal): Promise<WantView> {
  return request<WantView>(wantPath(id), { headers: bearer(token), signal });
}

export function huntWant(id: string, token: string): Promise<WantView> {
  return request<WantView>(wantPath(id, "/hunt"), {
    method: "POST",
    headers: bearer(token),
  });
}

export function targetWant(id: string, token: string, listingId: string): Promise<WantView> {
  return request<WantView>(wantPath(id, "/target"), {
    method: "POST",
    headers: bearer(token),
    body: JSON.stringify({ listing_id: listingId }),
  });
}

export function signup(email: string, password: string): Promise<UserPublic> {
  return request<UserPublic>("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function login(email: string, password: string): Promise<UserPublic> {
  return request<UserPublic>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function getMe(signal?: AbortSignal): Promise<UserPublic> {
  return request<UserPublic>("/api/auth/me", { signal });
}

export async function logout(): Promise<void> {
  await fetch(apiUrl("/api/auth/logout"), { method: "POST", credentials: "include" });
}

export function searchListings(
  q: string,
  category?: Category | null,
  signal?: AbortSignal,
): Promise<SearchResponse> {
  const payload: { q: string; category?: Category } = { q };
  if (category) payload.category = category;
  return request<SearchResponse>("/api/search", {
    method: "POST",
    body: JSON.stringify(payload),
    signal,
  });
}

export function getBots(signal?: AbortSignal): Promise<BotsResponse> {
  return request<BotsResponse>("/api/bots", { signal });
}

export function getNotifications(signal?: AbortSignal): Promise<NotificationsResponse> {
  return request<NotificationsResponse>("/api/notifications", { signal });
}

export function markNotificationsRead(ids?: string[]): Promise<NotificationsResponse> {
  return request<NotificationsResponse>("/api/notifications/read", {
    method: "POST",
    body: JSON.stringify(ids ? { ids } : {}),
  });
}

export function acceptNegotiation(id: string): Promise<Negotiation> {
  return request<Negotiation>(`/api/negotiations/${encodeURIComponent(id)}/accept`, {
    method: "POST",
  });
}

export function getActivity(signal?: AbortSignal): Promise<{ events: { at: string; message: string }[] }> {
  return request("/api/activity", { signal });
}

export function getDeals(signal?: AbortSignal): Promise<DealsResponse> {
  return request<DealsResponse>("/api/deals", { signal });
}

export function openThread(body: {
  listing_id: string;
  intent: "offer" | "message" | "bot";
  text?: string;
  amount?: number;
  limit?: number;
}): Promise<ThreadView> {
  return request<ThreadView>("/api/threads", { method: "POST", body: JSON.stringify(body) });
}

export function getThread(id: string, signal?: AbortSignal): Promise<ThreadView> {
  return request<ThreadView>(`/api/threads/${encodeURIComponent(id)}`, { signal });
}

export function postThreadMessage(
  id: string,
  body: { text?: string; amount?: number; kind: "text" | "offer" | "counter" | "accept" | "decline" },
): Promise<ThreadView> {
  return request<ThreadView>(`/api/threads/${encodeURIComponent(id)}/messages`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function setThreadMode(id: string, mode: "manual" | "bot"): Promise<ThreadView> {
  return request<ThreadView>(`/api/threads/${encodeURIComponent(id)}/mode`, {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}

export function setThreadLimit(id: string, limit: number): Promise<ThreadView> {
  return request<ThreadView>(`/api/threads/${encodeURIComponent(id)}/limit`, {
    method: "POST",
    body: JSON.stringify({ limit }),
  });
}
