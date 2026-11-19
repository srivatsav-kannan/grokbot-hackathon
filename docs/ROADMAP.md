# Roadmap

2-hour build. If a phase slips, cut in the order below. Do not shrink the feed to save a later demo.

## Cut order

1. **Core feed + scam/price badges.** Photo grid, listing detail, verdict and trust on every card. Appraiser and Inspector results are global.
2. **Wants + hunt.** Composer, `parse_want`, match list, buyer agent negotiating inside a server-only max, seller agent inside a server-only minimum. Direct-at-one-listing included here.
3. **Grok Bot integration demo.** Same want API called from a user's Grok Bot, with the fake-token flow in `docs/GROKBOT_INTEGRATION.md`.

Ship 1 before 2, and 2 before 3. A strong feed with badges beats a bot demo on a broken board.

## T+0:00 – 0:15 · Plan and freeze

- Docs on `main`. API paths and field names frozen in `docs/ARCHITECTURE.md`.
- Skeleton after that: `frontend/`, `backend/` with one module per agent, SQLite, `.env.example`, `.gitignore`.

## T+0:15 – 1:00 · Parallel build

Seed about a dozen listings (`origin: "seed"`), placeholder images, three categories.

- **@unclesdad:** visual system, photo feed, and the want screens against the contract.
- **@srivatsav-kannan:** `parse_want`, `match_listings`, Buyer and Seller, Appraiser, Inspector, Lister, leak test.
- **@heruirayli:** SQLite, routes (including wants), Scout pipeline stub.

## T+1:00 – 1:30 · Integration

- Scout → store → appraise → inspect on anything new. Seed rows can stay if a category is empty.
- Agents call Grok through the seam. Key from `GROK_API_KEY` only.
- Frontend uses the live API.
- End-to-end: feed → listing, photo → published listing, want → hunt → outcome.

## T+1:30 – 1:50 · Polish, phone, deploy

- One obvious next step on each screen. Phone width, no horizontal scroll, no hover-only actions.
- One public HTTPS service. No login on the feed.

## T+1:50 – 2:00 · Submit

- Fill every README section.
- Repo public.
- Grok Bot session export with personal info removed (names, emails, phone numbers, tokens).
- Submit the public link and the repo.

## Stretch

Only after feed, badges, want hunt, and the public link work on a phone.

- Live Grok Bot skill walkthrough in the demo.
- Richer comps, a one-line "why this verdict", neighborhood filter, a second sell photo.

## Cut list

Drop from the top if the clock slips. Do not cut the public link, the phone layout, or the price and trust badges.

1. Grok Bot live demo. The HTTP API can exist without a rehearsed bot.
2. Want composer polish. A plain text box plus status is enough.
3. Negotiation visual polish. A plain transcript with deal / no deal is enough.
4. Search box (`q=`). Category chips are enough.
5. Live Scout. Stay on labeled seed data if fetching is late or blocked.
6. Live Grok calls. Stubs are fine if the key or latency gets in the way.
7. Extra motion. The calmer layout wins.

## Best Design checklist

- [ ] Visual craft on the feed, the listing, and the want status.
- [ ] A person can scan a card and know the next step.
- [ ] Photos first, verdict and trust on the card, less chrome than a classic classifieds page.
- [ ] AI changes the flow: say a want, agents find and haggle; every listing is priced and scam-checked. Not a chat box beside an old form.
- [ ] Live public link on a laptop and a phone. No login.
- [ ] Built with Grok Bot, and the README says how.
