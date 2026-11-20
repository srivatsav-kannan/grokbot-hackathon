import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { acceptNegotiation, ApiError, getListing, getNegotiation } from "../api/client";
import { TranscriptSkeleton, ErrorNotice, Missing } from "../components/States";
import { formatStamp, formatUsd, FROM_LABEL, KIND_LABEL } from "../lib/format";
import { useTitle } from "../lib/title";
import type { ListingDetail, Negotiation } from "../types";

type Load =
  | { status: "loading" }
  | { status: "ready"; negotiation: Negotiation; listing: ListingDetail | null }
  | { status: "error"; error: ApiError };

export function NegotiationPage() {
  const { id = "" } = useParams();
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [accepting, setAccepting] = useState(false);
  const [acceptError, setAcceptError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setLoad({ status: "loading" });
    getNegotiation(id, controller.signal)
      .then(async (negotiation) => {
        let listing: ListingDetail | null = null;
        try {
          listing = await getListing(negotiation.listing_id, controller.signal);
        } catch {
          listing = null;
        }
        if (!controller.signal.aborted) setLoad({ status: "ready", negotiation, listing });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const error =
          err instanceof ApiError ? err : new ApiError("unreachable", "The board didn't respond.", 0);
        setLoad({ status: "error", error });
      });
    return () => controller.abort();
  }, [id, attempt]);

  const negotiation = load.status === "ready" ? load.negotiation : null;
  useTitle(negotiation ? (negotiation.outcome === "deal" ? "Deal" : "No deal") : "Negotiation");

  if (load.status === "loading") {
    return (
      <div className="wrap board">
        <TranscriptSkeleton />
      </div>
    );
  }

  if (load.status === "error") {
    if (load.error.status === 404) {
      return (
        <div className="wrap board">
          <Missing title="This negotiation isn't on the board">
            <p>The transcript may have expired, or the link is out of date.</p>
            <Link className="back-link" to="/">
              Back to the board
            </Link>
          </Missing>
        </div>
      );
    }
    return (
      <div className="wrap board">
        <ErrorNotice
          title="The transcript didn't load"
          message={load.error.message}
          onRetry={() => setAttempt((value) => value + 1)}
        />
      </div>
    );
  }

  if (!negotiation) return null;
  const deal = negotiation.outcome === "deal";

  return (
    <article className="wrap board negotiation" data-negotiation-id={negotiation.id} data-outcome={negotiation.outcome}>
      <p className="back-row">
        <Link className="back-link" to={`/listings/${negotiation.listing_id}`}>
          {load.listing ? load.listing.title : "Back to the listing"}
        </Link>
      </p>
      <header className="outcome">
        <h1 className={deal ? "outcome-word outcome-deal" : "outcome-word outcome-no_deal"}>
          {deal ? "Deal" : "No deal"}
        </h1>
        <p>
          {negotiation.accepted
            ? "You accepted this deal."
            : "This negotiation is finished. The transcript shows offers only. Price limits stay on the server."}
        </p>
        {deal && !negotiation.accepted ? (
          <button
            type="button"
            className="button-primary"
            disabled={accepting}
            onClick={() => {
              setAccepting(true);
              setAcceptError("");
              acceptNegotiation(negotiation.id)
                .then(() => setAttempt((value) => value + 1))
                .catch((err: unknown) => {
                  setAcceptError(err instanceof ApiError ? err.message : "Could not accept the deal.");
                  setAccepting(false);
                });
            }}
          >
            {accepting ? "Accepting…" : "Accept deal"}
          </button>
        ) : null}
        {acceptError ? <p className="form-error">{acceptError}</p> : null}
      </header>
      {negotiation.messages.length === 0 ? (
        <p>No offers were recorded.</p>
      ) : (
        <ol className="transcript">
          {negotiation.messages.map((message, index) => (
            <li key={`${message.at}-${index}`} data-from={message.from} data-kind={message.kind}>
              <span className="spoke" aria-hidden="true" />
              <div>
                <p className="turn-meta">
                  <span className="who">{FROM_LABEL[message.from]}</span>
                  <span className="kind">{KIND_LABEL[message.kind]}</span>
                  {message.amount != null ? <span className="amt">{formatUsd(message.amount)}</span> : null}
                </p>
                <p className="turn-text">{message.text}</p>
                <time dateTime={message.at}>{formatStamp(message.at)}</time>
              </div>
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}
