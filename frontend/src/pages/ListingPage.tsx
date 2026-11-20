import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, getListing, mediaUrl, openThread } from "../api/client";
import { Marks } from "../components/Marks";
import { PhotoFrame } from "../components/PhotoFrame";
import { Price } from "../components/Price";
import { DetailSkeleton, ErrorNotice, Missing } from "../components/States";
import {
  CATEGORY_LABEL,
  formatUsd,
  formatWhen,
  loginPath,
  verdictReason,
} from "../lib/format";
import { useTitle } from "../lib/title";
import type { ListingDetail } from "../types";

type Load =
  | { status: "loading" }
  | { status: "ready"; listing: ListingDetail }
  | { status: "error"; error: ApiError };

export function ListingPage() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [offerState, setOfferState] = useState<"idle" | "working" | "error">("idle");
  const [offerMessage, setOfferMessage] = useState("");
  const offerKey = useRef<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoad({ status: "loading" });
    getListing(id, controller.signal)
      .then((listing) => {
        if (!controller.signal.aborted) setLoad({ status: "ready", listing });
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        const error =
          err instanceof ApiError ? err : new ApiError("unreachable", "The board didn't respond.", 0);
        setLoad({ status: "error", error });
      });
    return () => controller.abort();
  }, [id, attempt]);

  const listing = load.status === "ready" ? load.listing : null;
  useTitle(listing ? listing.title : "Listing");

  async function onOffer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!listing) return;
    setOfferState("working");
    setOfferMessage("");
    try {
      offerKey.current ??= crypto.randomUUID();
      const thread = await openThread(
        {
          listing_id: listing.id,
          intent: "offer",
          text: "I'd like to make an offer.",
        },
        offerKey.current,
      );
      navigate(`/deals/${thread.id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        navigate(loginPath(`/listings/${listing.id}`));
        return;
      }
      setOfferState("error");
      setOfferMessage(err instanceof ApiError ? err.message : "The offer didn't go through.");
    }
  }

  if (load.status === "loading") {
    return (
      <div className="wrap board">
        <DetailSkeleton />
      </div>
    );
  }

  if (load.status === "error") {
    if (load.error.status === 404) {
      return (
        <div className="wrap board">
          <Missing title="This listing isn't on the board">
            <p>It may have been removed, or the link is out of date.</p>
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
          title="The listing didn't load"
          message={load.error.message}
          onRetry={() => setAttempt((value) => value + 1)}
        />
      </div>
    );
  }

  if (!listing) return null;

  return (
    <article
      className="wrap board detail"
      data-listing-id={listing.id}
      data-category={listing.category}
      data-price={listing.price}
      data-verdict={listing.appraisal.verdict}
      data-trust={listing.inspection.trust_level}
      data-origin={listing.origin}
      data-neighborhood={listing.neighborhood}
    >
      <p className="back-row">
        <Link className="back-link" to="/">
          Back to the board
        </Link>
      </p>
      <div className="detail-top">
        <div className="detail-photo">
          {listing.photos.length > 0 ? (
            listing.photos.map((src, index) => (
              <PhotoFrame
                key={src}
                src={mediaUrl(src)}
                alt={index === 0 ? `${listing.title}, photo` : ""}
                label={CATEGORY_LABEL[listing.category]}
                eager={index === 0}
              />
            ))
          ) : (
            <PhotoFrame src="" alt="" label={CATEGORY_LABEL[listing.category]} />
          )}
        </div>
        <div className="detail-summary">
          <p className="eyebrow-place">{listing.neighborhood}</p>
          <h1>{listing.title}</h1>
          <Price className="price price-lg" amount={listing.price} />
          <p className="posted">
            <time dateTime={listing.posted_at}>{formatWhen(listing.posted_at)}</time>
            <span> · {CATEGORY_LABEL[listing.category]}</span>
          </p>
          <Marks
            verdict={listing.appraisal.verdict}
            trust={listing.inspection.trust_level}
            origin={listing.origin}
            sourceName={listing.source_name}
          />
          <p className="description">{listing.description}</p>
          {listing.sold_for != null ? <p className="sold-line">Sold for {formatUsd(listing.sold_for)}</p> : null}
          {listing.source_url ? (
            <p>
              <a className="back-link" href={listing.source_url} rel="noreferrer">
                View on Craigslist
              </a>
            </p>
          ) : null}
          {listing.outreach ? (
            <div className="advice">
              <p>Suggested offer {formatUsd(listing.outreach.amount)}</p>
              <pre>{listing.outreach.message}</pre>
            </div>
          ) : null}

          <div className="actions">
            {listing.origin === "scout" || listing.sold_for != null ? null : (
              <>
                <form method="post" action="/api/threads" onSubmit={onOffer}>
                  <input type="hidden" name="listing_id" value={listing.id} />
                  <button
                    type="submit"
                    className="button-primary"
                    data-action="make-offer"
                    disabled={offerState === "working"}
                  >
                    {offerState === "working" ? "Making an offer…" : "Make an offer"}
                  </button>
                </form>
                {offerState === "error" ? (
                  <p className="form-error" role="alert">
                    {offerMessage}
                  </p>
                ) : null}
              </>
            )}
          </div>
        </div>
      </div>

      <section
        className="appraisal"
        aria-labelledby="comps-heading"
        data-estimated={listing.appraisal.estimated_value}
        data-low={listing.appraisal.low}
        data-high={listing.appraisal.high}
      >
        <h2 id="comps-heading">Price against comps</h2>
        <p>{verdictReason(listing.appraisal.verdict)}</p>
        <p className="range">
          Estimated <Price amount={listing.appraisal.estimated_value} className="inline-price" />.
          Comparable range {formatUsd(listing.appraisal.low)}–{formatUsd(listing.appraisal.high)}.
        </p>
        {listing.appraisal.comps.length > 0 ? (
          <table className="comps">
            <caption>Comparable listings</caption>
            <thead>
              <tr>
                <th scope="col">Listing</th>
                <th scope="col" className="num">
                  Price
                </th>
              </tr>
            </thead>
            <tbody>
              {listing.appraisal.comps.map((comp) => (
                <tr key={`${comp.title}-${comp.price}`}>
                  <td>
                    {comp.url ? (
                      <a href={comp.url} rel="noreferrer">
                        {comp.title}
                      </a>
                    ) : (
                      comp.title
                    )}
                  </td>
                  <td className="num">{formatUsd(comp.price)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p>No comparable listings were attached.</p>
        )}
      </section>

      <section className="trust" aria-labelledby="trust-heading">
        <h2 id="trust-heading">Trust check</h2>
        <Marks verdict={listing.appraisal.verdict} trust={listing.inspection.trust_level} />
        {listing.inspection.signals.length > 0 ? (
          <ul className="signals">
            {listing.inspection.signals.map((signal) => (
              <li key={signal.code} data-signal={signal.code}>
                {signal.reason}
              </li>
            ))}
          </ul>
        ) : (
          <p>No issues flagged.</p>
        )}
      </section>
    </article>
  );
}
