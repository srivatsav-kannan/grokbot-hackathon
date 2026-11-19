# Tasks

Three tracks. **Person A**, **Person B**, and **Person C** are placeholders — fill in names in person, not in the repo.

Contract and badge vocabulary live in `docs/ARCHITECTURE.md`. Do not rename fields after T+0:15 without the other two.

## Person A · Frontend and design

**Owns:** `frontend/` (Vite, React, TypeScript, styling).

**Phases**

- **T+0:00 – 0:15.** Confirm the list, detail, lister, publish, and negotiation JSON with Person C. Lock badge labels: Good deal / Fair / Overpriced and High / Medium / Low trust.
- **T+0:15 – 1:00.**
  - [ ] Visual system: type, color, spacing. Photo-first, calm, high contrast. Works with placeholder images.
  - [ ] Feed: responsive photo grid, category chips (Bikes / Computers / Furniture).
  - [ ] Card: photo, title, asking price, neighborhood, verdict badge, trust badge. Seed rows marked Sample.
  - [ ] Listing detail: description, comps, signal reasons, primary action "Make an offer".
  - [ ] Sell flow: pick a photo, show the Lister draft, edit, publish.
  - [ ] Negotiation view: transcript and outcome only. No inputs for hidden limits.
- **T+1:00 – 1:30.** Point the app at the live API (`VITE_API_BASE_URL` empty in production). Drop mocks that drift from the contract.
- **T+1:30 – 1:50.** Mobile pass and visual polish. Tap targets and type sizes that work on a phone. Empty and error states.
- **T+1:50 – 2:00.** Hand Person C three screenshots or notes for the README (feed desktop, feed phone, one flow).

**Handoffs**

- Needs Person C's server reachable with seed listings by the end of the parallel build.
- Needs Person B's verdict and trust enums to stay stable (already frozen in the architecture doc).
- Gives Person C the production `frontend/dist` build command and any required env names before deploy.

## Person B · AI agents

**Owns:** `backend/app/agents/appraiser.py`, `inspector.py`, `lister.py`, `negotiator.py`, their prompts, and `backend/tests/test_no_price_limit_leak.py`.

**Phases**

- **T+0:00 – 0:15.** Read the Appraisal, Inspection, Negotiation, and PriceLimits sections. Agree the leak test name and the forbidden keys: `buyer_max`, `seller_min`, `price_limits`.
- **T+0:15 – 1:00.**
  - [ ] Appraiser: comps plus `estimated_value`, `low`, `high`, and `verdict` using the range rule in the architecture doc.
  - [ ] Inspector: `trust_level` and plain-language `signals`.
  - [ ] Lister: photo in, draft title / description / category / `suggested_price` out. One function is the Grok seam.
  - [ ] Negotiator: Buyer and Seller agents exchange offers inside the server-only limits and finish `deal` or `no_deal`. Offers in the transcript stay inside the limits. The limits themselves are not in the return value.
  - [ ] Leak test: negotiation HTTP payloads and the OpenAPI schema do not contain the forbidden keys. Fails if a response model grows those fields.
- **T+1:00 – 1:30.** Replace stub bodies with Grok calls behind the same return shapes. Read `GROK_API_KEY` from the environment only. Timeouts fall back to the stub result rather than a broken page.
- **T+1:30 – 1:50.** Tighten prompts only if the feed is already up. Skip prompt tweaks if deploy is behind.
- **T+1:50 – 2:00.** Note in the README draft (for Person C) what the agents actually decide. No session logs that contain limits or personal data.

**Handoffs**

- Needs Person C's `Listing` and `PriceLimits` access (functions or tables) before wiring agents to the DB. Until then, pure functions over dicts are fine.
- Gives Person A stable badge values and Person C functions they can call from the route handlers: `appraise`, `inspect`, `draft_from_photo`, `negotiate`.
- Tells Person C immediately if a Grok call would require logging prompt text that includes limits. That logging must not ship.

## Person C · Data, API, and ship

**Owns:** `backend/app/main.py`, models, SQLite access, `backend/app/agents/scout.py`, seed data, `Dockerfile` or the single-service config, `.env.example`, `.gitignore`, and the root `README.md` fill-in.

**Phases**

- **T+0:00 – 0:15.** Skeleton matching the contract: routers for the six endpoints plus `POST /api/listings`. Empty agent calls can return fixtures.
- **T+0:15 – 1:00.**
  - [ ] SQLite tables for Listing, Appraisal, Inspection, Negotiation, and PriceLimits.
  - [ ] Seed about a dozen listings across bikes, computers, and furniture. `origin: "seed"`. Placeholder images. No real names, emails, or phone numbers. PriceLimits rows exist only in the database.
  - [ ] Endpoints match `docs/ARCHITECTURE.md` request and response shapes.
  - [ ] Scout module documented with the rules: public pages only, a few pages per run, no sign-in / posting / messaging / accounts, cache, stop and report on CAPTCHA or block. No live Craigslist fetch in the first hour.
  - [ ] `.env.example` lists `GROK_API_KEY`, optional `GROK_API_BASE_URL`, optional `CORS_ORIGINS`. Empty values.
- **T+1:00 – 1:30.** Plug Person B's functions into the routes. Scout run writes listings, then appraisal and inspection. CORS only for local Vite if needed.
- **T+1:30 – 1:50.**
  - [ ] Serve `frontend/dist` from FastAPI.
  - [ ] Deploy one public HTTPS URL. Check laptop and phone. No login.
- **T+1:50 – 2:00.**
  - [ ] README sections all filled (see root stub).
  - [ ] Repo public.
  - [ ] Grok Bot session export added with personal info removed.
  - [ ] Submit the link.

**Handoffs**

- Publishes the base URL (local, then public) to Person A.
- Does not put seed price limits in any file under `frontend/` or in API examples that get copied into the client.
- If Scout is blocked, ship seed data and say so in the README instead of working around the block.

## Integration checkpoints

| When | All three confirm |
| --- | --- |
| T+0:15 | Contract frozen. Skeleton exists. No open questions on field names. |
| T+1:00 | Feed renders seed listings with both badges. Lister, Appraiser, Inspector, and negotiation endpoints respond. Leak test passes. |
| T+1:30 | One deployed URL loads the feed on a phone-sized window. Photo → draft and offer → outcome work against that server. |
| T+2:00 | README complete, repo public, session export cleaned, link submitted. |
