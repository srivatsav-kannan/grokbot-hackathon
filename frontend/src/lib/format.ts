import type { Category, SortKey, Verdict } from "../types";

export const CATEGORY_LABEL: Record<Category, string> = {
  bikes: "Bikes",
  computers: "Computers",
  furniture: "Furniture",
};

export const VERDICT_LABEL: Record<Verdict, string> = {
  good_deal: "Good deal",
  fair: "Fair",
  overpriced: "Overpriced",
};

export const TRUST_LABEL = {
  high: "High trust",
  medium: "Medium trust",
  low: "Low trust",
} as const;

export const KIND_LABEL = {
  offer: "Offer",
  counter: "Counter",
  accept: "Accept",
  decline: "Decline",
} as const;

export const FROM_LABEL = {
  buyer: "Buyer",
  seller: "Seller",
} as const;

export const WANT_STATUS_LABEL = {
  open: "Open",
  hunting: "Hunting",
  negotiating: "Negotiating",
  done: "Done",
} as const;

export const CATEGORIES: Category[] = ["bikes", "computers", "furniture"];

export function verdictReason(verdict: Verdict): string {
  if (verdict === "good_deal") return "The asking price is under the comparable range.";
  if (verdict === "overpriced") return "The asking price is over the comparable range.";
  return "The asking price sits inside the comparable range.";
}

export function formatUsd(amount: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatWhen(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

export function formatStamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function parseCategory(value: string | null): Category | null {
  if (value === "bikes" || value === "computers" || value === "furniture") return value;
  return null;
}

export function parseSort(value: string | null): SortKey {
  if (value === "price_asc" || value === "price_desc" || value === "newest") return value;
  return "newest";
}

export function boardHref(parts: { q?: string; category?: string | null; sort?: string | null }): string {
  const params = new URLSearchParams();
  const q = parts.q?.trim();
  if (q) params.set("q", q);
  if (parts.category === "bikes" || parts.category === "computers" || parts.category === "furniture") {
    params.set("category", parts.category);
  }
  if (parts.sort === "price_asc" || parts.sort === "price_desc") params.set("sort", parts.sort);
  const query = params.toString();
  return query ? `/?${query}` : "/";
}
