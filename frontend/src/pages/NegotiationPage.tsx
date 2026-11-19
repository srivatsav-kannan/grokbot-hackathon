import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, getListing, getNegotiation } from "../api/client";
import { TranscriptSkeleton, ErrorNotice, Missing } from "../components/States";
import { formatStamp, formatUsd, FROM_LABEL, KIND_LABEL } from "../lib/format";
import { gsap, ScrollTrigger, useReducedMotion } from "../lib/scroll";
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
  const root = useRef<HTMLOListElement>(null);
  const reduced = useReducedMotion();

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

  useLayoutEffect(() => {
    const list = root.current;
    if (!list || reduced || !negotiation) return;
    const ctx = gsap.context(() => {
      const spokes = gsap.utils.toArray<HTMLElement>(".spoke", list);
      spokes.forEach((spoke) => {
        const item = spoke.parentElement;
        if (!item) return;
        gsap.fromTo(
          spoke,
          { scaleY: 0 },
          {
            scaleY: 1,
            ease: "none",
            scrollTrigger: {
              trigger: item,
              start: "top 80%",
              end: "top 40%",
              scrub: true,
            },
          },
        );
      });
      ScrollTrigger.refresh();
    }, list);
    return () => ctx.revert();
  }, [negotiation, reduced]);

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
        <p>This negotiation is finished. The transcript shows offers only. Price limits stay on the server.</p>
      </header>
      {negotiation.messages.length === 0 ? (
        <p>No offers were recorded.</p>
      ) : (
        <ol className="transcript" ref={root}>
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
