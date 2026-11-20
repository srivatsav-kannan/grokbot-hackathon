import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, getDeals, getThread, postThreadMessage } from "../api/client";
import { ErrorNotice } from "../components/States";
import { useAuth } from "../auth";
import { formatUsd, loginPath } from "../lib/format";
import { useTitle } from "../lib/title";
import type { DealsResponse, ThreadView } from "../types";

type Row = {
  key: string;
  title: string;
  summary: string;
  threadId: string | null;
};

function rowsOf(deals: DealsResponse): Row[] {
  const rows: Row[] = [];
  for (const bot of deals.buyer_bots) {
    if (bot.threads.length === 0) {
      rows.push({ key: bot.id, title: bot.label, summary: "Watching for matches", threadId: null });
    }
    for (const thread of bot.threads) {
      rows.push({ key: thread.id, title: bot.label, summary: thread.summary, threadId: thread.id });
    }
  }
  for (const thread of deals.direct) {
    rows.push({ key: thread.id, title: thread.title, summary: thread.summary, threadId: thread.id });
  }
  for (const box of deals.listings) {
    for (const thread of box.threads) {
      rows.push({ key: thread.id, title: box.title, summary: thread.summary, threadId: thread.id });
    }
  }
  return rows;
}

export function DealsPage() {
  const { threadId } = useParams();
  const navigate = useNavigate();
  const { user, loading } = useAuth();
  const [deals, setDeals] = useState<DealsResponse | null>(null);
  const [thread, setThread] = useState<ThreadView | null>(null);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState("");
  const [amount, setAmount] = useState("");
  const [sending, setSending] = useState(false);
  useTitle("Deals");

  useEffect(() => {
    if (loading) return;
    if (!user) {
      navigate(loginPath("/deals"));
    }
  }, [loading, user, navigate]);

  useEffect(() => {
    if (!user) return;
    const controller = new AbortController();
    getDeals(controller.signal)
      .then((payload) => {
        if (!controller.signal.aborted) setDeals(payload);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof ApiError ? err.message : "Deals didn't load.");
      });
    return () => controller.abort();
  }, [user, threadId]);

  useEffect(() => {
    if (!user || !threadId) {
      setThread(null);
      return;
    }
    const controller = new AbortController();
    getThread(threadId, controller.signal)
      .then((payload) => {
        if (!controller.signal.aborted) setThread(payload);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof ApiError ? err.message : "That conversation didn't load.");
      });
    return () => controller.abort();
  }, [user, threadId]);

  async function send(event: FormEvent, kind: "text" | "offer" | "accept") {
    event.preventDefault();
    if (!thread) return;
    const dollars = amount.trim() ? Number(amount) : undefined;
    setSending(true);
    setError("");
    try {
      const next = await postThreadMessage(thread.id, {
        kind: kind === "text" && dollars ? "offer" : kind,
        text: draft || (kind === "accept" ? "I accept." : ""),
        amount: dollars,
      });
      setThread(next);
      setDraft("");
      setAmount("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The message didn't send.");
    } finally {
      setSending(false);
    }
  }

  const rows = deals ? rowsOf(deals) : [];

  return (
    <div className={`wrap deals-layout${threadId ? " has-thread" : ""}`}>
      <aside className="deals-list" aria-label="Conversations">
        <h1>Deals</h1>
        {deals && deals.buyer_bots.length > 0 ? (
          <section className="deal-records">
            <h2>Buyer bots</h2>
            <ul>
              {deals.buyer_bots.map((bot) => (
                <li key={bot.id}>
                  <strong>{bot.label}</strong>
                  <span>
                    {bot.status === "negotiating" ? "Negotiating" : bot.status === "done" ? "Done" : "Watching"} ·{" "}
                    {bot.matches?.length ?? 0} matches · {bot.threads.length} conversations
                  </span>
                  {(bot.matches ?? []).slice(0, 4).map((match) => (
                    <Link key={match.listing_id} to={`/listings/${match.listing_id}`}>
                      {match.title} · {formatUsd(match.price)} · {match.source_name}
                    </Link>
                  ))}
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        {deals?.completed && deals.completed.length > 0 ? (
          <section className="deal-records">
            <h2>Completed deals</h2>
            <ul>
              {deals.completed.map((done) => (
                <li key={done.id}>
                  <Link to={done.thread_id ? `/deals/${done.thread_id}` : `/listings/${done.listing_id}`}>
                    <strong>{done.title}</strong>
                    <span>
                      {done.role === "buyer" ? "Bought" : "Sold"} for {formatUsd(done.price)} ·{" "}
                      {new Date(done.at).toLocaleString()}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        <h2 className="deal-records-head">Conversations</h2>
        {rows.length === 0 ? <p className="agent-note">No conversations yet.</p> : null}
        <ul>
          {rows.map((row) => (
            <li key={row.key}>
              {row.threadId ? (
                <Link to={`/deals/${row.threadId}`} aria-current={row.threadId === threadId ? "page" : undefined}>
                  <strong>{row.title}</strong>
                  <span>{row.summary}</span>
                </Link>
              ) : (
                <p>
                  <strong>{row.title}</strong>
                  <span>{row.summary}</span>
                </p>
              )}
            </li>
          ))}
        </ul>
      </aside>
      <section className="deals-chat" aria-label="Conversation">
        {!threadId ? <p className="agent-note">Choose a conversation.</p> : null}
        {thread ? (
          <>
            <header className="deals-chat-head">
              <h2>{thread.listing_title}</h2>
              <p>
                {thread.status === "deal" ? "Sold" : thread.summary} · asking {formatUsd(thread.listing_price)}
              </p>
              <Link to={`/listings/${thread.listing_id}`}>View listing</Link>
            </header>
            <ol className="bubbles">
              {thread.messages.map((message) => {
                const mine =
                  thread.role === "buyer"
                    ? message.author.startsWith("buyer")
                    : message.author.startsWith("seller");
                return (
                  <li key={`${message.at}-${message.text}`} className={mine ? "mine" : "theirs"}>
                    <p>{message.text}</p>
                    {message.amount != null ? <span>{formatUsd(message.amount)}</span> : null}
                  </li>
                );
              })}
            </ol>
            {thread.status === "deal" ? (
              <p className="sold-line">This listing is sold.</p>
            ) : (
              <form className="composer" onSubmit={(event) => void send(event, "text")}>
                <label>
                  Offer
                  <input
                    inputMode="numeric"
                    name="amount"
                    value={amount}
                    onChange={(event) => setAmount(event.target.value)}
                    placeholder="200"
                  />
                </label>
                <label className="composer-text">
                  Message
                  <input
                    name="text"
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    placeholder="Write a message"
                  />
                </label>
                <button type="submit" disabled={sending}>
                  Send
                </button>
                {(() => {
                  const last = [...thread.messages].reverse().find((m) => m.amount != null);
                  const theirs =
                    last && !last.author.startsWith(thread.role === "buyer" ? "buyer" : "seller");
                  return theirs && last ? (
                    <button
                      type="button"
                      disabled={sending}
                      onClick={(event) => {
                        setAmount(String(last.amount));
                        void postThreadMessage(thread.id, { kind: "accept", amount: last.amount ?? undefined, text: "Deal." })
                          .then((next) => {
                            setThread(next);
                            event.preventDefault();
                          })
                          .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Accept failed."));
                      }}
                    >
                      Accept {formatUsd(last.amount ?? 0)}
                    </button>
                  ) : null;
                })()}
              </form>
            )}
          </>
        ) : null}
        {error ? (
          <ErrorNotice title="Deals" message={error} onRetry={() => setError("")} />
        ) : null}
      </section>
    </div>
  );
}
