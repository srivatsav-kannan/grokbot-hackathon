"""End-to-end check of every Fairlot flow against a running server.

Usage: python scripts/e2e.py https://fairlot.onrender.com [--demo]

It signs up throwaway accounts (qa-<run>@example.com), lists an item as a test
seller, and buys only that test seller's items, so sample listings stay
available. --demo also exercises the shared demo account's waiting offer, which
uses it up, so only pass it against a local server.
"""

from __future__ import annotations

import base64
import json
import secrets
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8765"
DEMO = "--demo" in sys.argv
RUN = secrets.token_hex(3)
PHOTO = "data:image/png;base64," + base64.b64encode(
    bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
        "1f15c4890000000d49444154789c6360000002000100e221bc330000000049454e44ae426082"
    )
).decode()
results: list[tuple[str, bool, str]] = []


class Client:
    def __init__(self) -> None:
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        self.seen: list[str] = []

    def call(self, method: str, path: str, body: object | None = None, key: str | None = None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(BASE + "/api" + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if key:
            req.add_header("Idempotency-Key", key)
        try:
            with self.opener.open(req, timeout=120) as resp:
                raw = resp.read().decode()
                status = resp.status
        except urllib.error.HTTPError as err:
            raw = err.read().decode()
            status = err.code
        self.seen.append(raw)
        try:
            return status, json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return status, raw


def check(name: str, ok: bool, detail: object = "") -> None:
    results.append((name, bool(ok), str(detail)[:160]))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {str(detail)[:300]}"), flush=True)


def amounts(thread: dict) -> list[int]:
    return [m["amount"] for m in thread.get("messages", []) if m.get("amount") is not None]


def main() -> int:
    anon = Client()
    status, health = anon.call("GET", "/health")
    check("health ok", status == 200 and health.get("ok"), health)

    status, feed = anon.call("GET", "/listings")
    rows = feed["listings"]
    origins = {r["origin"] for r in rows}
    scouted = [r for r in rows if r["origin"] == "scout"]
    check("feed has sample listings", any(r["origin"] == "seed" for r in rows), origins)
    check("feed has Craigslist listings", len(scouted) > 0, len(scouted))
    if scouted:
        _, one = anon.call("GET", f"/listings/{scouted[0]['id']}")
        check(
            "Craigslist listing links to craigslist.org",
            "craigslist.org" in (one.get("source_url") or ""),
            one.get("source_url"),
        )
        newest = max(r["posted_at"] for r in scouted)
        check("Craigslist listings are recent", newest >= time.strftime("%Y-%m-%d", time.gmtime(time.time() - 3 * 86400)), newest)
    check("photos on every card", all(r["photos"] for r in rows), [r["id"] for r in rows if not r["photos"]][:5])

    status, found = anon.call("POST", "/search", {"q": "bike"})
    check("search returns listings", status == 200 and len(found.get("listings", [])) > 0, status)

    # Accounts
    seller, buyer, other = Client(), Client(), Client()
    pw = "pass-" + RUN + "-x"
    for c, who in ((seller, "s"), (buyer, "b"), (other, "o")):
        status, _ = c.call("POST", "/auth/signup", {"email": f"qa-{who}-{RUN}@example.com", "password": pw})
        check(f"signup {who}", status == 201, status)
    status, _ = buyer.call("POST", "/auth/signup", {"email": f"qa-b-{RUN}@example.com", "password": pw})
    check("duplicate signup refused", status == 400, status)
    status, _ = anon.call("POST", "/auth/login", {"email": f"qa-b-{RUN}@example.com", "password": "wrong-pass-1"})
    check("wrong password refused", status == 401, status)

    status, demo_login = Client().call("POST", "/auth/login", {"email": "demo@fairlot.app", "password": "fairlot-demo"})
    check("demo login works", status == 200, demo_login)

    # Selling: publish, idempotent
    listing_body = {
        "category": "bikes",
        "title": f"QA test bike {RUN}",
        "description": "Test listing from the end-to-end check.",
        "price": 400,
        "photos": [PHOTO],
        "neighborhood": "Palo Alto",
        "minimum": 337,
    }
    status, pub = seller.call("POST", "/listings", listing_body, key=f"pub-{RUN}")
    check("seller publishes a listing", status == 201 and pub.get("mine") is True, (status, pub))
    lid = pub.get("id")
    status, again = seller.call("POST", "/listings", listing_body, key=f"pub-{RUN}")
    check("publish retry with same key returns same listing", again.get("id") == lid, again.get("id"))
    status, again2 = seller.call("POST", "/listings", listing_body)
    check("publish double-click without key returns same listing", again2.get("id") == lid, again2.get("id"))
    check("appraisal and trust check attached", pub.get("appraisal", {}).get("verdict") and pub.get("inspection", {}).get("trust_level"), pub.get("appraisal"))

    _, mine = seller.call("GET", f"/listings/{lid}")
    check("seller sees the listing as theirs", mine.get("mine") is True, mine.get("mine"))
    status, own = seller.call("POST", "/threads", {"listing_id": lid, "intent": "offer", "amount": 300, "limit": 350})
    check("seller cannot buy own listing", status == 400 and "your listing" in json.dumps(own).lower(), (status, own))
    _, theirs = buyer.call("GET", f"/listings/{lid}")
    check("buyer does not see it as theirs", theirs.get("mine") is False, theirs.get("mine"))

    # Buying: manual offer, idempotent thread
    status, t1 = buyer.call("POST", "/threads", {"listing_id": lid, "intent": "offer", "amount": 250, "limit": 390, "text": "I can offer $250."}, key=f"o1-{RUN}")
    check("buyer offer opens a thread", status == 201 and t1.get("id"), (status, t1))
    tid = t1["id"]
    n1 = len(t1["messages"])
    check("seller bot answers below its minimum with a counter", t1["messages"][-1]["author"] == "seller_bot", t1["messages"][-1])
    _, t1b = buyer.call("POST", "/threads", {"listing_id": lid, "intent": "offer", "amount": 250, "limit": 390}, key=f"o1-{RUN}")
    check("offer retry with same key: same thread, no new messages", t1b["id"] == tid and len(t1b["messages"]) == n1, (t1b["id"], len(t1b["messages"])))
    _, t1c = buyer.call("POST", "/threads", {"listing_id": lid, "intent": "offer", "amount": 260}, key=f"o2-{RUN}")
    check("second offer from the same buyer reuses the thread", t1c["id"] == tid and len(t1c["messages"]) == n1, (t1c["id"], len(t1c["messages"])))
    _, again_view = buyer.call("GET", f"/listings/{lid}")
    check("listing points the buyer back to their conversation", again_view.get("my_thread_id") == tid, again_view.get("my_thread_id"))
    _, msg = buyer.call("POST", f"/threads/{tid}/messages", {"kind": "text", "text": "Is Saturday morning ok?"}, key=f"m1-{RUN}")
    n2 = len(msg["messages"])
    _, msg2 = buyer.call("POST", f"/threads/{tid}/messages", {"kind": "text", "text": "Is Saturday morning ok?"}, key=f"m1-{RUN}")
    check("message retry with same key is not duplicated", len(msg2["messages"]) == n2, (n2, len(msg2["messages"])))
    check("buyer never sees the seller minimum", "337" not in "".join(buyer.seen), "leak")

    # Seller view
    _, sdeals = seller.call("GET", "/deals")
    box = next((b for b in sdeals["listings"] if b["listing_id"] == lid), None)
    check("seller's Deals lists the listing under Selling", box is not None, sdeals["listings"])
    check("seller sees the buyer's conversation", box is not None and any(t["id"] == tid for t in box["threads"]), box)
    _, sview = seller.call("GET", f"/threads/{tid}")
    check("seller sees own minimum in the thread", sview.get("role") == "seller" and sview.get("my_limit") == 337, (sview.get("role"), sview.get("my_limit")))
    check("seller never sees the buyer max", "390" not in "".join(seller.seen), "leak")
    _, notes = seller.call("GET", "/notifications")
    check("seller gets a notification", notes.get("unread", 0) > 0 or len(notes.get("notifications", [])) > 0, notes.get("unread"))

    # Buyer accepts the counter, sale closes once
    counter = amounts(msg2)[-1]
    _, acc = buyer.call("POST", f"/threads/{tid}/messages", {"kind": "accept", "amount": counter, "text": "Deal."}, key=f"a1-{RUN}")
    check("buyer accepts the counter", acc.get("status") == "deal", acc.get("status"))
    _, acc2 = buyer.call("POST", f"/threads/{tid}/messages", {"kind": "accept", "amount": counter, "text": "Deal."}, key=f"a2-{RUN}")
    check("second accept changes nothing", acc2.get("status") == "deal" and len(acc2["messages"]) == len(acc["messages"]), len(acc2["messages"]))
    _, bdeals = buyer.call("GET", "/deals")
    _, sdeals = seller.call("GET", "/deals")
    bc = [c for c in bdeals.get("completed", []) if c["listing_id"] == lid]
    sc = [c for c in sdeals.get("completed", []) if c["listing_id"] == lid]
    check("one completion record for the buyer", len(bc) == 1 and bc[0]["role"] == "buyer" and bc[0]["price"] == counter, bc)
    check("one completion record for the seller", len(sc) == 1 and sc[0]["role"] == "seller", sc)
    _, sold = anon.call("GET", f"/listings/{lid}")
    check("listing shows sold price", sold.get("sold_for") == counter, sold.get("sold_for"))
    status, late = other.call("POST", "/threads", {"listing_id": lid, "intent": "offer", "amount": 380, "limit": 400})
    check("nobody can offer on a sold listing", status == 400, (status, late))

    # Bot negotiation on a second test listing, approval step
    body2 = dict(listing_body, title=f"QA test desk {RUN}", category="furniture", price=300, minimum=241)
    _, pub2 = seller.call("POST", "/listings", body2, key=f"pub2-{RUN}")
    lid2 = pub2["id"]
    status, bot = other.call("POST", "/threads", {"listing_id": lid2, "intent": "bot", "limit": 289}, key=f"b1-{RUN}")
    check("bot negotiation reaches an agreement", status == 201 and bot.get("status") == "agreed", (status, bot.get("status"), bot.get("summary")))
    buyer_offers = [m["amount"] for m in bot.get("messages", []) if m["author"] == "buyer_bot" and m.get("amount") is not None]
    check("bot never offers above the buyer max", buyer_offers and all(a <= 289 for a in buyer_offers), buyer_offers)
    check("agreement is not a sale yet", not [c for c in other.call("GET", "/deals")[1].get("completed", []) if c["listing_id"] == lid2], "")
    price = amounts(bot)[-1] if amounts(bot) else None
    _, ap1 = other.call("POST", f"/threads/{bot['id']}/messages", {"kind": "accept", "amount": price, "text": "Approved."}, key=f"approve-{bot['id']}")
    _, ap2 = other.call("POST", f"/threads/{bot['id']}/messages", {"kind": "accept", "amount": price, "text": "Approved."}, key=f"approve-{bot['id']}")
    check("approve records the sale", ap1.get("status") == "deal", ap1.get("status"))
    check("double approve is idempotent", len(ap1["messages"]) == len(ap2["messages"]), (len(ap1["messages"]), len(ap2["messages"])))
    _, od = other.call("GET", "/deals")
    check("exactly one completion after approval", len([c for c in od["completed"] if c["listing_id"] == lid2]) == 1, od["completed"])

    # End conversation and scam guard on a third test listing
    body3 = dict(listing_body, title=f"QA test lamp {RUN}", category="furniture", price=120, minimum=97)
    _, pub3 = seller.call("POST", "/listings", body3, key=f"pub3-{RUN}")
    lid3 = pub3["id"]
    _, t3 = buyer.call("POST", "/threads", {"listing_id": lid3, "intent": "offer", "amount": 60, "limit": 110})
    _, scam = buyer.call("POST", f"/threads/{t3['id']}/messages", {"kind": "text", "text": "I'm overseas, I'll pay with gift cards and my shipper will pick it up."})
    check("seller bot ends a scam conversation", scam.get("status") == "declined" and scam["messages"][-1]["author"] == "seller_bot", scam["messages"][-1] if scam.get("messages") else scam)
    _, t4 = other.call("POST", "/threads", {"listing_id": lid3, "intent": "offer", "amount": 70, "limit": 110})
    _, ended = other.call("POST", f"/threads/{t4['id']}/messages", {"kind": "decline", "text": "I'm ending this conversation."}, key=f"end-{RUN}")
    check("buyer can end a conversation", ended.get("status") == "declined", ended.get("status"))
    _, seller_end = seller.call("GET", f"/threads/{t4['id']}")
    check("seller sees it ended", seller_end.get("status") == "declined", seller_end.get("status"))
    closer = Client()
    closer.call("POST", "/auth/signup", {"email": f"qa-c-{RUN}@example.com", "password": pw})
    _, t5 = closer.call("POST", "/threads", {"listing_id": lid3, "intent": "offer", "amount": 115, "limit": 120})
    check("seller bot accepts an offer above its minimum", t5.get("status") == "deal", t5.get("status"))
    _, feed_after = anon.call("GET", "/listings")
    visible = {r["id"] for r in feed_after["listings"]}
    check("sold items leave the feed", not ({lid, lid2, lid3} & visible), {lid, lid2, lid3} & visible)
    _, sample = anon.call("GET", "/listings/lst_01")
    check("sample listing has a seller profile", bool(sample.get("seller")), sample.get("seller"))
    if sample.get("seller"):
        _, prof = anon.call("GET", f"/sellers/{sample['seller']['id']}")
        check("seller page lists their other items", len(prof.get("listings", [])) >= 1, prof.get("name"))

    # Buyer bot from search
    _, w1 = buyer.call("POST", "/wants", {"text": f"chair under $200 qa {RUN}", "max_price": 200})
    _, w2 = buyer.call("POST", "/wants", {"text": f"chair under $200 qa {RUN}", "max_price": 200})
    check("starting the same buyer bot twice gives one bot", w1.get("id") == w2.get("id"), (w1.get("id"), w2.get("id")))
    status, h1 = buyer.call("POST", f"/wants/{w1['id']}/hunt")
    check("buyer bot hunt starts", status == 200, (status, str(h1)[:200]))

    def settle() -> dict:
        last, same = None, 0
        for _ in range(40):
            _, d = buyer.call("GET", "/deals")
            bot = next((b for b in d["buyer_bots"] if b["id"] == w1["id"]), {})
            shape = (len(bot.get("threads", [])), bot.get("status"))
            same = same + 1 if shape == last and bot.get("status") != "hunting" else 0
            last = shape
            if same >= 2:
                return bot
            time.sleep(3)
        return bot

    bot1 = settle()
    check("buyer bot found several listings", len(bot1.get("matches", [])) >= 1, len(bot1.get("matches", [])))
    check("buyer bot opened conversations", len(bot1.get("threads", [])) >= 1, len(bot1.get("threads", [])))
    buyer.call("POST", f"/wants/{w1['id']}/hunt")
    bot2 = settle()
    check("second hunt does not duplicate conversations", len(bot2.get("threads", [])) == len(bot1.get("threads", [])), (len(bot1.get("threads", [])), len(bot2.get("threads", []))))

    if DEMO:
        demo = Client()
        demo.call("POST", "/auth/login", {"email": "demo@fairlot.app", "password": "fairlot-demo"})
        _, dd = demo.call("GET", "/deals")
        lounge = dd["listings"][0] if dd["listings"] else None
        check("demo owns the lounge set with an offer waiting", lounge and lounge["threads"] and lounge["threads"][0]["summary"] == "Waiting on you", lounge)
        if lounge and lounge["threads"]:
            th = lounge["threads"][0]["id"]
            _, cv = demo.call("POST", f"/threads/{th}/messages", {"kind": "counter", "amount": 790, "text": "Could you do 790?"})
            check("demo seller can counter", cv["messages"][-1]["amount"] in (790, None) or cv.get("status") in ("deal", "agreed", "open"), cv["messages"][-1])
            _, mv = demo.call("POST", f"/threads/{th}/mode", {"mode": "bot"})
            check("demo seller hands it to the bot and it finishes", mv.get("status") in ("deal", "declined"), mv.get("status"))

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed (run {RUN})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
