import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, createWant, huntWant, listListings } from "../api/client";
import { Hero } from "../components/Hero";
import { ListingGrid } from "../components/ListingGrid";
import {
  EmptyCategory,
  EmptySearch,
  EmptySoon,
  ErrorNotice,
  LoadingGrid,
} from "../components/States";
import {
  boardHref,
  CATEGORY_LABEL,
  parseCategory,
  parseSort,
} from "../lib/format";
import { saveWant } from "../lib/session";
import { useTitle } from "../lib/title";
import type { ListingCard, SortKey } from "../types";

type Load =
  | { status: "loading" }
  | { status: "ready"; listings: ListingCard[] }
  | { status: "error"; error: ApiError };

function sortListings(rows: ListingCard[], sort: SortKey): ListingCard[] {
  const copy = [...rows];
  if (sort === "price_asc") {
    copy.sort((a, b) => a.price - b.price || b.posted_at.localeCompare(a.posted_at));
  } else if (sort === "price_desc") {
    copy.sort((a, b) => b.price - a.price || b.posted_at.localeCompare(a.posted_at));
  } else {
    copy.sort((a, b) => b.posted_at.localeCompare(a.posted_at));
  }
  return copy;
}

export function BoardPage() {
  const [params] = useSearchParams();
  const rawCategory = params.get("category");
  const category = parseCategory(rawCategory);
  const invalidCategory = Boolean(rawCategory) && category === null;
  const q = params.get("q")?.trim() ?? "";
  const sort = parseSort(params.get("sort"));
  const catalogue = q.length > 0;
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [agentState, setAgentState] = useState<"idle" | "working" | "error">("idle");
  const [agentMessage, setAgentMessage] = useState("");

  useTitle(catalogue ? `Results for ${q}` : "Fairlot");

  useEffect(() => {
    if (invalidCategory) {
      setLoad({
        status: "error",
        error: new ApiError("bad_request", "Category must be bikes, computers, or furniture.", 400),
      });
      return;
    }
    const controller = new AbortController();
    setLoad({ status: "loading" });
    listListings({ category, q, signal: controller.signal })
      .then((response) => {
        if (!controller.signal.aborted) setLoad({ status: "ready", listings: response.listings });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const error =
          err instanceof ApiError ? err : new ApiError("unreachable", "The board didn't respond.", 0);
        setLoad({ status: "error", error });
      });
    return () => controller.abort();
  }, [category, q, invalidCategory, attempt]);

  const listings = useMemo(
    () => (load.status === "ready" ? sortListings(load.listings, sort) : []),
    [load, sort],
  );

  async function askAgent() {
    if (!q) return;
    setAgentState("working");
    setAgentMessage("");
    try {
      const created = await createWant({ text: q, category });
      saveWant(created.id, created.access_token, q);
      await huntWant(created.id, created.access_token);
      window.location.assign(`/wants/${created.id}`);
    } catch (err) {
      setAgentState("error");
      setAgentMessage(err instanceof ApiError ? err.message : "The buyer agent didn't start.");
    }
  }

  const heading = catalogue
    ? "Search results"
    : category
      ? `Recent ${CATEGORY_LABEL[category].toLowerCase()}`
      : "Recent listings";

  return (
    <>
      {catalogue ? null : <Hero listings={load.status === "ready" ? listings : []} />}
      <div className="wrap board">
        {catalogue ? (
          <div className="catalogue-head">
            <h1>
              Results for <q>{q}</q>
            </h1>
            <form id="catalogue-sort" className="sort-form" method="get" action="/">
              <input type="hidden" name="q" value={q} />
              {category ? <input type="hidden" name="category" value={category} /> : null}
              <label htmlFor="sort">Sort</label>
              <select id="sort" name="sort" defaultValue={sort}>
                <option value="newest">Newest</option>
                <option value="price_asc">Price, low to high</option>
                <option value="price_desc">Price, high to low</option>
              </select>
              <button type="submit">Apply</button>
            </form>
          </div>
        ) : (
          <h2 className="section-title">{heading}</h2>
        )}

        {load.status === "loading" ? (
          <LoadingGrid label={catalogue ? "Loading results" : "Loading listings"} />
        ) : null}

        {load.status === "error" ? (
          <ErrorNotice
            title={catalogue ? "The search didn't go through" : "The board didn't respond"}
            message={load.error.message}
            onRetry={() => setAttempt((value) => value + 1)}
          />
        ) : null}

        {load.status === "ready" && listings.length > 0 ? (
          <>
            <p className="count" aria-live="polite">
              {listings.length === 1 ? "1 listing" : `${listings.length} listings`}
              {catalogue ? null : " on the board"}
            </p>
            <ListingGrid listings={listings} />
          </>
        ) : null}

        {load.status === "ready" && listings.length === 0 && catalogue ? (
          <EmptySearch query={q} category={category ? CATEGORY_LABEL[category] : undefined} />
        ) : null}
        {load.status === "ready" && listings.length === 0 && !catalogue && category ? (
          <EmptyCategory label={CATEGORY_LABEL[category]} />
        ) : null}
        {load.status === "ready" && listings.length === 0 && !catalogue && !category ? <EmptySoon /> : null}

        {catalogue ? (
          <div className="agent-row">
            <button type="button" data-action="hunt" onClick={askAgent} disabled={agentState === "working"}>
              {agentState === "working" ? "The buyer agent is negotiating…" : "Have the buyer agent negotiate"}
            </button>
            <Link className="back-link" to={boardHref({})}>
              Clear the search
            </Link>
            {agentState === "error" ? (
              <p className="form-error" role="alert">
                {agentMessage}
              </p>
            ) : null}
          </div>
        ) : null}
      </div>
    </>
  );
}
