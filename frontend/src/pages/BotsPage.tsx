import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { acceptNegotiation, ApiError, getBots } from "../api/client";
import { useAuth } from "../auth";
import { Marks } from "../components/Marks";
import { formatUsd, loginPath, WANT_STATUS_LABEL } from "../lib/format";
import { useTitle } from "../lib/title";
import type { BotsResponse, Negotiation } from "../types";

export function BotsPage() {
  const { user, loading } = useAuth();
  const [bots, setBots] = useState<BotsResponse | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useTitle("My bots");

  useEffect(() => {
    if (!user) return;
    const controller = new AbortController();
    getBots(controller.signal)
      .then((payload) => {
        if (!controller.signal.aborted) setBots(payload);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof ApiError ? err.message : "The bots didn't load.");
      });
    return () => controller.abort();
  }, [user, attempt]);

  if (loading) {
    return (
      <div className="wrap board">
        <p>Loading your bots…</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="wrap board">
        <h1>My bots</h1>
        <p>Log in to see the buyer bots you sent and the seller bot on each listing you published.</p>
        <Link className="button-primary" to={loginPath("/bots")}>
          Log in
        </Link>
      </div>
    );
  }

  return (
    <div className="wrap board bots">
      <h1>My bots</h1>
      <p className="lede">Buyer bots keep searching. Seller bots answer offers on the listings you published.</p>
      {error ? (
        <p className="form-error" role="alert">
          {error}{" "}
          <button type="button" onClick={() => setAttempt((value) => value + 1)}>
            Try again
          </button>
        </p>
      ) : null}

      <section aria-labelledby="buyer-bots">
        <h2 id="buyer-bots">Buyer bots</h2>
        {!bots || bots.buyers.length === 0 ? (
          <p>
            None yet. Search the board and choose <Link to="/">Send a buyer bot</Link>.
          </p>
        ) : (
          <ul className="bot-list">
            {bots.buyers.map((bot) => (
              <li key={bot.id}>
                <p className="status-label">{WANT_STATUS_LABEL[bot.status]}</p>
                <h3>{bot.text}</h3>
                <p>
                  {bot.matches.length} match{bot.matches.length === 1 ? "" : "es"}
                </p>
                <ul>
                  {bot.matches.slice(0, 3).map((match) => (
                    <li key={match.listing_id}>
                      <Link to={`/listings/${match.listing_id}`}>{match.title}</Link>
                      <span> {formatUsd(match.price)}</span>
                      <Marks
                        verdict={match.appraisal.verdict}
                        trust={match.inspection.trust_level}
                        origin={match.origin}
                        sourceName={match.source_name}
                      />
                    </li>
                  ))}
                </ul>
                {bot.recommendations.map((advice) => (
                  <div key={advice.listing_id} className="advice">
                    <p>
                      Suggested offer {formatUsd(advice.suggested_offer)} on {advice.title}. Copy this and send it
                      yourself.
                    </p>
                    <pre>{advice.message}</pre>
                  </div>
                ))}
                {bot.negotiations.map((item) => (
                  <Talk key={item.id} item={item} onAccepted={() => setAttempt((value) => value + 1)} />
                ))}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="seller-bots">
        <h2 id="seller-bots">Seller bots</h2>
        {!bots || bots.sellers.length === 0 ? (
          <p>
            None yet. <Link to="/sell">Sell from a photo</Link> and a seller bot watches that listing.
          </p>
        ) : (
          <ul className="bot-list">
            {bots.sellers.map((bot) => (
              <li key={bot.listing_id}>
                <h3>
                  <Link to={`/listings/${bot.listing_id}`}>{bot.title}</Link>
                </h3>
                <p>{formatUsd(bot.price)} asking. The seller bot stays above your private minimum.</p>
                {bot.negotiations.length === 0 ? <p>No offers yet.</p> : null}
                {bot.negotiations.map((item) => (
                  <Talk key={item.id} item={item} onAccepted={() => setAttempt((value) => value + 1)} />
                ))}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Talk({ item, onAccepted }: { item: Negotiation; onAccepted: () => void }) {
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const last = item.messages.slice(-2);

  async function accept() {
    setWorking(true);
    setError("");
    try {
      await acceptNegotiation(item.id);
      onAccepted();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not accept.");
      setWorking(false);
    }
  }

  return (
    <div className="talk">
      <p>
        <Link to={`/negotiations/${item.id}`}>{item.outcome === "deal" ? "Deal" : "No deal"}</Link>
        {item.accepted ? " · accepted" : ""}
      </p>
      <ul>
        {last.map((message, index) => (
          <li key={`${message.at}-${index}`}>
            {message.from === "buyer" ? "Buyer" : "Seller"}: {message.text}
          </li>
        ))}
      </ul>
      {item.outcome === "deal" && !item.accepted ? (
        <button type="button" onClick={() => void accept()} disabled={working}>
          {working ? "Accepting…" : "Accept deal"}
        </button>
      ) : null}
      {error ? <p className="form-error">{error}</p> : null}
    </div>
  );
}
