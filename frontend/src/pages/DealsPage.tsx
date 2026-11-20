import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, getDeals, getThread, postThreadMessage, setThreadLimit, setThreadMode } from "../api/client";
import { ErrorNotice } from "../components/States";
import { useAuth } from "../auth";
import { formatUsd, loginPath } from "../lib/format";
import { useTitle } from "../lib/title";
import type { DealsResponse, ThreadSummary, ThreadView } from "../types";

function ThreadLinks({ threads, current, label }: { threads: ThreadSummary[]; current?: string; label?: string }) {
  if (threads.length === 0) return null;
  return (
    <ul className="thread-links">
      {threads.map((thread) => (
        <li key={thread.id}>
          <Link to={`/deals/${thread.id}`} aria-current={thread.id === current ? "page" : undefined}>
            <strong>{label ?? thread.title}</strong>
            <span>{thread.summary}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function whoSaid(author: string, role: "buyer" | "seller"): string {
  const mine = author.startsWith(role);
  const bot = author.endsWith("_bot");
  if (mine) return bot ? "Your bot" : "You";
  const side = author.startsWith("buyer") ? "Buyer" : "Seller";
  return bot ? `${side}'s bot` : side;
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
  const sendKey = useRef<string | null>(null);
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
    const load = () =>
      getDeals(controller.signal)
        .then((payload) => {
          if (!controller.signal.aborted) setDeals(payload);
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return;
          setError(err instanceof ApiError ? err.message : "Deals didn't load.");
        });
    void load();
    const timer = window.setInterval(() => void load(), 6000);
    return () => {
      window.clearInterval(timer);
      controller.abort();
    };
  }, [user, threadId, thread?.status]);

  useEffect(() => {
    if (!user || !threadId) {
      setThread(null);
      return;
    }
    const controller = new AbortController();
    const load = () =>
      getThread(threadId, controller.signal)
        .then((payload) => {
          if (!controller.signal.aborted) setThread(payload);
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return;
          setError(err instanceof ApiError ? err.message : "That conversation didn't load.");
        });
    void load();
    const timer = window.setInterval(() => void load(), 5000);
    return () => {
      window.clearInterval(timer);
      controller.abort();
    };
  }, [user, threadId]);

  async function send(event: FormEvent, kind: "text" | "offer" | "accept") {
    event.preventDefault();
    if (!thread) return;
    const dollars = amount.trim() ? Number(amount) : undefined;
    setSending(true);
    setError("");
    try {
      sendKey.current ??= crypto.randomUUID();
      const next = await postThreadMessage(
        thread.id,
        {
          kind: kind === "text" && dollars ? "offer" : kind,
          text: draft || (kind === "accept" ? "I accept." : ""),
          amount: dollars,
        },
        sendKey.current,
      );
      sendKey.current = null;
      setThread(next);
      setDraft("");
      setAmount("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "The message didn't send.");
    } finally {
      setSending(false);
    }
  }

  async function changeMode(mode: "manual" | "bot") {
    if (!thread) return;
    setSending(true);
    setError("");
    try {
      setThread(await setThreadMode(thread.id, mode));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not switch.");
    } finally {
      setSending(false);
    }
  }

  async function saveLimit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!thread) return;
    const raw = String(new FormData(event.currentTarget).get("limit") ?? "").replace(/[^0-9]/g, "");
    if (!raw) return;
    setSending(true);
    setError("");
    try {
      setThread(await setThreadLimit(thread.id, Number(raw)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save your limit.");
    } finally {
      setSending(false);
    }
  }


  return (
    <div className={`wrap deals-layout${threadId ? " has-thread" : ""}`}>
      <aside className="deals-list" aria-label="Your deals">
        <h1>Deals</h1>
        {deals === null ? <p className="agent-note">Loading…</p> : null}

        <section className="deal-side">
          <h2>Buying</h2>
          {deals && deals.buyer_bots.length === 0 && deals.direct.length === 0 ? (
            <p className="agent-note">
              Nothing yet. Search for something and start a buyer bot, or open a listing and make a deal.
            </p>
          ) : null}
          {deals?.buyer_bots.map((bot) => (
            <div className="deal-group" key={bot.id}>
              <p className="deal-group-head">
                <strong>Buyer bot: {bot.label}</strong>
                <span>
                  {bot.status === "negotiating" ? "Negotiating" : bot.status === "done" ? "Done" : "Watching"} ·{" "}
                  {bot.matches?.length ?? 0} matches · {bot.threads.length} conversations
                </span>
              </p>
              <ThreadLinks threads={bot.threads} current={threadId} />
              {bot.threads.length === 0 && (bot.matches ?? []).length > 0 ? (
                <ul className="match-list">
                  {(bot.matches ?? []).slice(0, 4).map((match) => (
                    <li key={match.listing_id}>
                      <Link to={`/listings/${match.listing_id}`}>
                        {match.title} · {formatUsd(match.price)}
                        {match.source_name ? ` · ${match.source_name}` : ""}
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ))}
          {deals && deals.direct.length > 0 ? (
            <div className="deal-group">
              <p className="deal-group-head">
                <strong>Your offers</strong>
              </p>
              <ThreadLinks threads={deals.direct} current={threadId} />
            </div>
          ) : null}
        </section>

        <section className="deal-side">
          <h2>Selling</h2>
          {deals && deals.listings.length === 0 ? (
            <p className="agent-note">
              You have no listings. <Link to="/sell">Sell something</Link> and your seller bot answers offers for you.
            </p>
          ) : null}
          {deals?.listings.map((box) => (
            <div className="deal-group" key={box.listing_id}>
              <p className="deal-group-head">
                <Link to={`/listings/${box.listing_id}`}>
                  <strong>{box.title}</strong>
                </Link>
                <span>
                  {box.status === "sold" && box.sold_for != null
                    ? `Sold for ${formatUsd(box.sold_for)}`
                    : `Asking ${box.price != null ? formatUsd(box.price) : ""} · seller bot on`}{" "}
                  · {box.threads.length === 1 ? "1 conversation" : `${box.threads.length} conversations`}
                </span>
              </p>
              {box.threads.length === 0 ? <p className="agent-note">No offers yet.</p> : null}
              <ThreadLinks threads={box.threads} current={threadId} label="Offer from a buyer" />
            </div>
          ))}
        </section>

        {deals?.completed && deals.completed.length > 0 ? (
          <section className="deal-side">
            <h2>Completed</h2>
            <ul className="thread-links">
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
            {thread.status === "open" ? (
              <div className="thread-controls">
                <div className="mode-toggle" role="group" aria-label="Who is negotiating">
                  <button
                    type="button"
                    aria-pressed={(thread.role === "buyer" ? thread.buyer_mode : thread.seller_mode) === "manual"}
                    disabled={sending}
                    onClick={() => void changeMode("manual")}
                  >
                    I&apos;m talking
                  </button>
                  <button
                    type="button"
                    aria-pressed={(thread.role === "buyer" ? thread.buyer_mode : thread.seller_mode) === "bot"}
                    disabled={sending}
                    onClick={() => void changeMode("bot")}
                  >
                    My bot negotiates
                  </button>
                </div>
                <form className="limit-form" onSubmit={(event) => void saveLimit(event)} key={`${thread.id}-${thread.my_limit}`}>
                  <label>
                    Your private {thread.role === "buyer" ? "max" : "min"}
                    <span className="money-input">
                      <span aria-hidden="true">$</span>
                      <input name="limit" inputMode="numeric" defaultValue={thread.my_limit ?? ""} />
                    </span>
                  </label>
                  <button type="submit" disabled={sending}>
                    Save
                  </button>
                </form>
                <p className="offer-hint">
                  Only you see this number. Your bot never goes {thread.role === "buyer" ? "above" : "below"} it.
                </p>
                <button
                  type="button"
                  className="end-convo"
                  disabled={sending}
                  onClick={() => {
                    if (!window.confirm("End this conversation? Your bot stops negotiating here.")) return;
                    setSending(true);
                    setError("");
                    postThreadMessage(
                      thread.id,
                      { kind: "decline", text: "I'm ending this conversation." },
                      `end-${thread.id}-${thread.messages.length}`,
                    )
                      .then((next) => setThread(next))
                      .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Could not end it."))
                      .finally(() => setSending(false));
                  }}
                >
                  End conversation
                </button>
              </div>
            ) : null}
            <ol className="bubbles">
              {thread.messages.map((message) => {
                const mine =
                  thread.role === "buyer"
                    ? message.author.startsWith("buyer")
                    : message.author.startsWith("seller");
                return (
                  <li key={`${message.at}-${message.text}`} className={mine ? "mine" : "theirs"}>
                    <small className="who">{whoSaid(message.author, thread.role)}</small>
                    <p>{message.text}</p>
                    {message.amount != null ? <span>{formatUsd(message.amount)}</span> : null}
                  </li>
                );
              })}
            </ol>
            {thread.status === "agreed" ? (
              (() => {
                const agreed = [...thread.messages].reverse().find((m) => m.amount != null)?.amount ?? null;
                return thread.role === "buyer" ? (
                  <div className="approve-bar">
                    <p>Your bot agreed{agreed != null ? ` at ${formatUsd(agreed)}` : ""}. Nothing is final until you approve.</p>
                    <button
                      type="button"
                      className="button-primary"
                      disabled={sending}
                      onClick={() => {
                        setSending(true);
                        setError("");
                        postThreadMessage(
                          thread.id,
                          { kind: "accept", amount: agreed ?? undefined, text: "Approved." },
                          `approve-${thread.id}`,
                        )
                          .then((next) => setThread(next))
                          .catch((err: unknown) => setError(err instanceof ApiError ? err.message : "Approval failed."))
                          .finally(() => setSending(false));
                      }}
                    >
                      Approve deal{agreed != null ? ` at ${formatUsd(agreed)}` : ""}
                    </button>
                  </div>
                ) : (
                  <p className="sold-line">The buyer's bot agreed. Waiting for the buyer to approve.</p>
                );
              })()
            ) : thread.status === "deal" ? (
              <p className="sold-line">
                {thread.role === "buyer" ? "You bought this" : "You sold this"}
                {(() => {
                  const final = [...thread.messages].reverse().find((m) => m.amount != null)?.amount;
                  return final != null ? ` for ${formatUsd(final)}.` : ".";
                })()}
              </p>
            ) : thread.status === "declined" ? (
              <p className="sold-line">This conversation ended. Send a new message to reopen it.</p>
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
                        void postThreadMessage(
                          thread.id,
                          { kind: "accept", amount: last.amount ?? undefined, text: "Deal." },
                          `accept-${thread.id}-${thread.messages.length}`,
                        )
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
