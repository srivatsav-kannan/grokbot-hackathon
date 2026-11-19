# Roadmap

2-hour build. Times are minutes from the start of the build window. If a phase slips, drop items in the cut list before shrinking the feed.

## T+0:00 – 0:15 · Plan and freeze

- This docs commit is on `main`.
- API contract in `docs/ARCHITECTURE.md` is frozen: paths, field names, verdict values, trust levels.
- Repo skeleton only after the contract is agreed: `frontend/`, `backend/` with one module per agent, SQLite file location, `.env.example`, `.gitignore`. No extra features in the skeleton.

## T+0:15 – 1:00 · Parallel build

Work against the frozen contract and a seed dataset of about a dozen listings (bikes, computers, furniture), labeled `origin: "seed"`, placeholder images.

- **Person A:** visual system and the photo feed from seed JSON or the live list endpoint.
- **Person B:** agent stubs that already return the contract shapes, plus the leak test.
- **Person C:** SQLite, seed load, and the REST handlers the other two call.

Stay inside owned folders (see `docs/TASKS.md`) so the three branches merge cleanly.

## T+1:00 – 1:30 · Integration

- Scout writes real public listings in the same `Listing` shape (still polite and small). Seed rows can remain if a category comes back empty.
- Appraiser, Inspector, Lister, and Negotiator call Grok through the single seam. Key from `GROK_API_KEY` only.
- Frontend uses the live API only. Remove any local mock that disagrees with the server.
- First end-to-end path: feed → listing → offer, and photo → draft → published listing.

## T+1:30 – 1:50 · Polish, phone, deploy

- Design pass: type, spacing, badges, empty and error states. One obvious next step on each screen.
- Mobile pass at a phone width. No horizontal scroll, no hover-only actions.
- Deploy the single FastAPI service (static build + API) to a public HTTPS link.
- Open that link on a laptop and a phone. No login wall.

## T+1:50 – 2:00 · Submit

- Fill every README section listed in the root `README.md`.
- Make the repo public.
- Add the Grok Bot session export with personal info removed (names, emails, phone numbers, tokens).
- Submit the public link and the repo.

## Stretch goals

Only after the feed, listing page, photo sell flow, negotiation transcript, and public link work on a phone.

- Richer comp list (more than a couple of links) on the listing page.
- Short "why this verdict" sentence from the Appraiser next to the badge.
- Neighborhood filter in addition to category.
- A second photo on the sell flow.

## Cut list

Drop from the top if the clock slips. Do not cut the public link, the phone layout, or the price and trust badges.

1. Negotiation visual polish. A plain transcript with deal / no deal is enough.
2. Search box (`q=`). Category chips are enough.
3. Live Scout. Stay on labeled seed data if fetching public pages is late or gets blocked.
4. Live Grok calls. Keep the stubs if the key or latency gets in the way; the seam stays so a call can be turned on without a redesign.
5. Extra copy or animation. Shipping the calmer layout beats a motion pass.

## Best Design checklist

- [ ] Visual craft: layout, type, color, and spacing feel deliberate on the feed and the listing.
- [ ] Clarity: a person can scan a card and know the next step.
- [ ] Clearly better than a classic text classifieds page: photos first, less chrome, verdict and trust on the card.
- [ ] AI changes the flow: badges, a listing written from a photo, and an agent negotiation. Not a chat box beside an old form.
- [ ] Live public link works on a laptop and a phone. No login.
- [ ] Built with Grok Bot, and the README says how.
