import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, getWant, huntWant } from "../api/client";
import { Marks } from "../components/Marks";
import { ErrorNotice, Missing, TranscriptSkeleton } from "../components/States";
import { formatUsd, WANT_STATUS_LABEL } from "../lib/format";
import { tokenFor } from "../lib/session";
import { useTitle } from "../lib/title";
import type { WantView } from "../types";

type Load =
  | { status: "loading" }
  | { status: "ready"; want: WantView }
  | { status: "error"; error: ApiError }
  | { status: "no-session" };

export function WantPage() {
  const { id = "" } = useParams();
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [working, setWorking] = useState(false);

  const want = load.status === "ready" ? load.want : null;
  useTitle(want ? want.text : "Buyer agent");

  useEffect(() => {
    const token = tokenFor(id);
    if (!token) {
      setLoad({ status: "no-session" });
      return;
    }
    const controller = new AbortController();
    setLoad({ status: "loading" });
    getWant(id, token, controller.signal)
      .then((next) => {
        if (!controller.signal.aborted) setLoad({ status: "ready", want: next });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const error =
          err instanceof ApiError ? err : new ApiError("unreachable", "The board didn't respond.", 0);
        setLoad({ status: "error", error });
      });
    return () => controller.abort();
  }, [id, attempt]);

  async function onHunt() {
    const token = tokenFor(id);
    if (!token) return;
    setWorking(true);
    try {
      const next = await huntWant(id, token);
      setLoad({ status: "ready", want: next });
    } catch (err) {
      setLoad({
        status: "error",
        error: err instanceof ApiError ? err : new ApiError("unreachable", "The board didn't respond.", 0),
      });
    } finally {
      setWorking(false);
    }
  }

  if (load.status === "loading") {
    return (
      <div className="wrap board">
        <TranscriptSkeleton />
      </div>
    );
  }

  if (load.status === "no-session") {
    return (
      <div className="wrap board">
        <Missing title="This search isn't available in this session">
          <p>
            The buyer agent keeps this search on the server. Open it from the browser session that
            started it, or run a new search.
          </p>
          <Link className="back-link" to="/">
            New search
          </Link>
        </Missing>
      </div>
    );
  }

  if (load.status === "error") {
    if (load.error.status === 404 || load.error.status === 401) {
      return (
        <div className="wrap board">
          <Missing title="This search isn't available">
            <p>{load.error.message}</p>
            <Link className="back-link" to="/">
              New search
            </Link>
          </Missing>
        </div>
      );
    }
    return (
      <div className="wrap board">
        <ErrorNotice
          title="The buyer agent didn't respond"
          message={load.error.message}
          onRetry={() => setAttempt((value) => value + 1)}
        />
      </div>
    );
  }

  if (!want) return null;

  return (
    <article className="wrap board want" data-want-id={want.id} data-status={want.status}>
      <p className="back-row">
        <Link className="back-link" to="/">
          Back to the board
        </Link>
      </p>
      <p className="status-label">{WANT_STATUS_LABEL[want.status]}</p>
      <h1>{want.text}</h1>
      <p className="lede">
        Matches and outcomes are below. A private ceiling, if you named one, is not shown here.
      </p>
      <dl className="criteria">
        <div>
          <dt>Category</dt>
          <dd>{want.criteria.category ?? "Any"}</dd>
        </div>
        <div>
          <dt>Area</dt>
          <dd>{want.criteria.area ?? "Bay Area"}</dd>
        </div>
        <div>
          <dt>Keywords</dt>
          <dd>{want.criteria.keywords.length > 0 ? want.criteria.keywords.join(", ") : "None"}</dd>
        </div>
      </dl>

      {want.status === "open" ? (
        <button type="button" className="button-primary" data-action="hunt" onClick={onHunt} disabled={working}>
          {working ? "The buyer agent is negotiating…" : "Start the hunt"}
        </button>
      ) : null}

      <section aria-labelledby="matches-heading">
        <h2 id="matches-heading">Matches</h2>
        {want.matches.length === 0 ? (
          <p>The buyer agent didn't find a match.</p>
        ) : (
          <ul className="match-list">
            {want.matches.map((match) => (
              <li key={match.listing_id} data-listing-id={match.listing_id}>
                <Link to={`/listings/${match.listing_id}`}>
                  <span className="price">{formatUsd(match.price)}</span>
                  <span className="lot-title">{match.title}</span>
                  <span className="match-reason">{match.reason}</span>
                  <Marks verdict={match.appraisal.verdict} trust={match.inspection.trust_level} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="outcomes-heading">
        <h2 id="outcomes-heading">Outcomes</h2>
        {want.negotiations.length === 0 ? (
          <p>No negotiation yet.</p>
        ) : (
          <ul className="outcome-list">
            {want.negotiations.map((item) => (
              <li key={item.id}>
                <Link to={`/negotiations/${item.id}`}>
                  {item.outcome === "deal" ? "Deal" : "No deal"}
                  <span className="match-reason"> Open the transcript</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </article>
  );
}
