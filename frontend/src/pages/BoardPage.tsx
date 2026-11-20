import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError, createWant, huntWant, listListings, searchListings } from "../api/client";
import { useAuth } from "../auth";
import { ActivityPanel } from "../components/ActivityPanel";
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
  CATEGORIES,
  CATEGORY_LABEL,
  loginPath,
  parseCategory,
  parseSort,
} from "../lib/format";
import { saveWant } from "../lib/session";
import { useTitle } from "../lib/title";
import type { Category, ListingCard, Origin, SortKey } from "../types";
import { Marks } from "../components/Marks";
import { PhotoFrame } from "../components/PhotoFrame";
import { Price } from "../components/Price";
import { mediaUrl } from "../api/client";

type Load =
  | { status: "loading" }
  | { status: "ready"; listings: ListingCard[]; related: ListingCard[]; scouted: boolean }
  | { status: "error"; error: ApiError };

function originRank(origin: Origin): number {
  if (origin === "lister") return 0;
  if (origin === "seed") return 1;
  return 2;
}

function sortListings(rows: ListingCard[], sort: SortKey): ListingCard[] {
  const copy = [...rows];
  copy.sort((a, b) => {
    const rank = originRank(a.origin) - originRank(b.origin);
    if (rank !== 0) return rank;
    if (sort === "price_asc") return a.price - b.price || b.posted_at.localeCompare(a.posted_at);
    if (sort === "price_desc") return b.price - a.price || b.posted_at.localeCompare(a.posted_at);
    return b.posted_at.localeCompare(a.posted_at);
  });
  return copy;
}

export function BoardPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const rawCategory = params.get("category");
  const category = parseCategory(rawCategory);
  const invalidCategory = Boolean(rawCategory) && category === null;
  const q = params.get("q")?.trim() ?? "";
  const sort = parseSort(params.get("sort"));
  const rawPlace = params.get("place");
  const place = rawPlace === "external" || rawPlace === "fairlot" ? rawPlace : "all";
  const catalogue = q.length > 0;
  const { user } = useAuth();
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
    const listingsRequest = catalogue
      ? searchListings(q, category, controller.signal).then((response) => ({
          listings: response.listings,
          scouted: response.scouted,
        }))
      : listListings({ category, signal: controller.signal }).then((response) => ({
          listings: response.listings,
          scouted: false,
        }));
    listingsRequest
      .then((response) => {
        if (controller.signal.aborted) return;
        setLoad({
          status: "ready",
          listings: response.listings,
          related: [],
          scouted: response.scouted,
        });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const error =
          err instanceof ApiError ? err : new ApiError("unreachable", "The board didn't respond.", 0);
        setLoad({ status: "error", error });
      });
    return () => controller.abort();
  }, [category, q, invalidCategory, attempt]);

  const listings = useMemo(() => {
    const rows = load.status === "ready" ? sortListings(load.listings, sort) : [];
    if (place === "fairlot") return rows.filter((item) => item.origin === "lister");
    if (place === "external") return rows.filter((item) => item.origin === "scout");
    return rows;
  }, [load, sort, place]);
  const scouted = load.status === "ready" ? load.scouted : false;

  async function askAgent() {
    if (!q) return;
    if (!user) {
      sessionStorage.setItem("fairlot-pending-search", q);
      navigate(loginPath(`/?q=${encodeURIComponent(q)}`));
      return;
    }
    setAgentState("working");
    setAgentMessage("");
    try {
      const created = await createWant({ text: q, category });
      saveWant(created.id, created.access_token, q);
      await huntWant(created.id, created.access_token);
      navigate("/bots");
    } catch (err) {
      setAgentState("error");
      setAgentMessage(err instanceof ApiError ? err.message : "The buyer bot didn't start.");
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
          <div className="catalogue">
            <FilterBar q={q} category={category} sort={sort} place={place} />
            <div className="catalogue-main">
              <header className="catalogue-head">
                <h1>
                  Results for <q>{q}</q>
                </h1>
                {load.status === "ready" ? (
                  <p className="count" aria-live="polite">
                    {listings.length === 1 ? "1 listing" : `${listings.length} listings`}
                    {scouted ? " · Scout just checked public listings" : ""}
                  </p>
                ) : null}
              </header>
              {load.status === "loading" ? (
                <LoadingGrid label={q ? "Searching, and asking Scout if the board is empty" : "Loading results"} />
              ) : null}
              {load.status === "error" ? (
                <ErrorNotice
                  title="The search didn't go through"
                  message={load.error.message}
                  onRetry={() => setAttempt((value) => value + 1)}
                />
              ) : null}
              {load.status === "ready" && listings.length > 0 ? (
                <ul className="catalogue-rows" id="listing-grid">
                  {listings.slice(0, 6).map((listing) => (
                    <CatalogueRow key={listing.id} listing={listing} />
                  ))}
                </ul>
              ) : null}
              {load.status === "ready" && listings.length === 0 ? (
                <EmptySearch query={q} category={category ? CATEGORY_LABEL[category] : undefined} />
              ) : null}
              <div className="agent-row">
                <button type="button" data-action="hunt" onClick={askAgent} disabled={agentState === "working"}>
                  {agentState === "working" ? "Sending the buyer bot…" : "Send a buyer bot"}
                </button>
                <p className="agent-note">
                  It keeps searching, watches for price drops, and negotiates with Fairlot sellers.
                </p>
                <Link className="back-link" to={boardHref({})}>
                  Clear the search
                </Link>
                {agentState === "error" ? (
                  <p className="form-error" role="alert">
                    {agentMessage}
                  </p>
                ) : null}
              </div>
            </div>
          </div>
        ) : (
          <>
            <h2 className="section-title">{heading}</h2>
            {load.status === "loading" ? <LoadingGrid label="Loading listings" /> : null}
            {load.status === "error" ? (
              <ErrorNotice
                title="The board didn't respond"
                message={load.error.message}
                onRetry={() => setAttempt((value) => value + 1)}
              />
            ) : null}
            {load.status === "ready" && listings.length > 0 ? (
              <>
                <p className="count" aria-live="polite">
                  {listings.length === 1 ? "1 listing" : `${listings.length} listings`} on the board
                </p>
                <ListingGrid listings={listings} />
              </>
            ) : null}
            {load.status === "ready" && listings.length === 0 && category ? (
              <EmptyCategory label={CATEGORY_LABEL[category]} />
            ) : null}
            {load.status === "ready" && listings.length === 0 && !category ? <EmptySoon /> : null}
            <ActivityPanel />
          </>
        )}
      </div>
    </>
  );
}

function FilterBar({
  q,
  category,
  sort,
  place,
}: {
  q: string;
  category: Category | null;
  sort: SortKey;
  place: string;
}) {
  const navigate = useNavigate();
  return (
    <aside className="catalogue-side" aria-label="Filter results">
      <h2>Category</h2>
      <nav className="cats cats-stack" aria-label="Filter by category">
        <Link to={boardHref({ q, sort })} aria-current={category ? undefined : "true"}>
          All
        </Link>
        {CATEGORIES.map((item) => (
          <Link
            key={item}
            to={boardHref({ q, category: item, sort })}
            aria-current={category === item ? "true" : undefined}
          >
            {CATEGORY_LABEL[item]}
          </Link>
        ))}
      </nav>
      <form id="catalogue-sort" className="sort-form" method="get" action="/">
        <input type="hidden" name="q" value={q} />
        {category ? <input type="hidden" name="category" value={category} /> : null}
        <label htmlFor="sort">Sort</label>
        <select
          id="sort"
          name="sort"
          value={sort}
          onChange={(event) => {
            navigate(boardHref({ q, category, sort: event.target.value }));
          }}
        >
          <option value="newest">Newest</option>
          <option value="price_asc">Price, low to high</option>
          <option value="price_desc">Price, high to low</option>
        </select>
        <button type="submit">Apply</button>
      </form>
      <h2>Where</h2>
      <nav className="cats cats-stack" aria-label="Filter by source">
        <Link to={boardHref({ q, category, sort })} aria-current={place === "all" ? "true" : undefined}>
          Anywhere
        </Link>
        <Link
          to={boardHref({ q, category, sort, place: "fairlot" })}
          aria-current={place === "fairlot" ? "true" : undefined}
        >
          Fairlot
        </Link>
        <Link
          to={boardHref({ q, category, sort, place: "external" })}
          aria-current={place === "external" ? "true" : undefined}
        >
          Elsewhere
        </Link>
      </nav>
    </aside>
  );
}

function CatalogueRow({ listing }: { listing: ListingCard }) {
  const photo = listing.photos[0] ? mediaUrl(listing.photos[0]) : "";
  return (
    <li
      className="cat-row"
      id={`listing-${listing.id}`}
      data-listing-id={listing.id}
      data-category={listing.category}
      data-price={listing.price}
      data-verdict={listing.appraisal.verdict}
      data-trust={listing.inspection.trust_level}
      data-origin={listing.origin}
      data-neighborhood={listing.neighborhood}
    >
      <Link to={`/listings/${listing.id}`}>
        <PhotoFrame src={photo} alt="" label={CATEGORY_LABEL[listing.category]} />
        <div>
          <Price amount={listing.price} />
          <h2 className="lot-title">{listing.title}</h2>
          <p className="lot-place">{listing.neighborhood}</p>
          <Marks
            verdict={listing.appraisal.verdict}
            trust={listing.inspection.trust_level}
            origin={listing.origin}
            sourceName={listing.source_name}
          />
        </div>
      </Link>
    </li>
  );
}
