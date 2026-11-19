import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
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
  CATEGORIES,
  CATEGORY_LABEL,
  parseCategory,
  parseSort,
} from "../lib/format";
import { saveWant } from "../lib/session";
import { useTitle } from "../lib/title";
import type { Category, ListingCard, SortKey } from "../types";
import { Marks } from "../components/Marks";
import { PhotoFrame } from "../components/PhotoFrame";
import { Price } from "../components/Price";
import { mediaUrl } from "../api/client";

type Load =
  | { status: "loading" }
  | { status: "ready"; listings: ListingCard[]; related: ListingCard[] }
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
  const navigate = useNavigate();
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
    const listingsRequest = listListings({ category, q, signal: controller.signal });
    const relatedRequest = catalogue
      ? listListings({ signal: controller.signal })
      : Promise.resolve({ listings: [] as ListingCard[] });
    Promise.all([listingsRequest, relatedRequest])
      .then(([response, more]) => {
        if (controller.signal.aborted) return;
        const ids = new Set(response.listings.map((item) => item.id));
        const pool = more.listings.filter((item) => !ids.has(item.id));
        const sameCategory = category ? pool.filter((item) => item.category === category) : pool;
        const related = (sameCategory.length > 0 ? sameCategory : pool).slice(0, 4);
        setLoad({ status: "ready", listings: response.listings, related });
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
  const related = load.status === "ready" ? load.related : [];

  async function askAgent() {
    if (!q) return;
    setAgentState("working");
    setAgentMessage("");
    try {
      const created = await createWant({ text: q, category });
      saveWant(created.id, created.access_token, q);
      await huntWant(created.id, created.access_token);
      navigate(`/wants/${created.id}`);
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
          <div className="catalogue">
            <FilterBar q={q} category={category} sort={sort} />
            <div className="catalogue-main">
              <header className="catalogue-head">
                <h1>
                  Results for <q>{q}</q>
                </h1>
                {load.status === "ready" ? (
                  <p className="count" aria-live="polite">
                    {listings.length === 1 ? "1 listing" : `${listings.length} listings`}
                  </p>
                ) : null}
              </header>
              {load.status === "loading" ? <LoadingGrid label="Loading results" /> : null}
              {load.status === "error" ? (
                <ErrorNotice
                  title="The search didn't go through"
                  message={load.error.message}
                  onRetry={() => setAttempt((value) => value + 1)}
                />
              ) : null}
              {load.status === "ready" && listings.length > 0 ? (
                <ul className="catalogue-rows" id="listing-grid">
                  {listings.map((listing) => (
                    <CatalogueRow key={listing.id} listing={listing} />
                  ))}
                </ul>
              ) : null}
              {load.status === "ready" && listings.length === 0 ? (
                <EmptySearch query={q} category={category ? CATEGORY_LABEL[category] : undefined} />
              ) : null}
              {related.length > 0 ? (
                <section className="related" aria-labelledby="also-heading">
                  <h2 id="also-heading">Also on the board</h2>
                  <ListingGrid listings={related} />
                </section>
              ) : null}
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
}: {
  q: string;
  category: Category | null;
  sort: SortKey;
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
          />
        </div>
      </Link>
    </li>
  );
}
