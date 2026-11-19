# Tasks

Handles only. Contract: `docs/ARCHITECTURE.md`. Bot client: `docs/GROKBOT_INTEGRATION.md`.

## Person A · @unclesdad · Frontend and design

**Owns:** `frontend/`.

Wants screens are new: a composer ("road bike under $400 in SF"), a want status view (matches with verdict and trust, transcript, deal / no deal), and a control to point the buyer agent at one open listing. Still no inputs for a max, a minimum, or a token pasted into the page copy. The rest of this track is unchanged.

**Phases**

- **T+0:00 – 0:15.** Confirm list, detail, lister, publish, negotiation, and want JSON with @heruirayli. Lock badge labels: Good deal / Fair / Overpriced and High / Medium / Low trust.
- **T+0:15 – 1:00.**
  - [ ] Visual system: type, color, spacing. Photo-first, calm, high contrast.
  - [ ] Feed: responsive photo grid, category chips (Bikes / Computers / Furniture).
  - [ ] Card: photo, title, asking price, neighborhood, verdict badge, trust badge. Seed rows marked Sample.
  - [ ] Listing detail: description, comps, signal reasons, primary action to direct the buyer agent here (and the existing offer action).
  - [ ] Sell flow: pick a photo, show the Lister draft, edit, publish.
  - [ ] Negotiation view: transcript and outcome only.
  - [ ] Want composer and want status (matches, badges, outcomes).
- **T+1:00 – 1:30.** Live API only. `VITE_API_BASE_URL` empty in production.
- **T+1:30 – 1:50.** Mobile pass. Empty and error states.
- **T+1:50 – 2:00.** Three screenshots or notes for the README (feed desktop, feed phone, want flow).

**Handoffs.** Needs a server with seed listings. Badge enums stay frozen. Hands @heruirayli the `frontend/dist` build command and env names before deploy.

## Person B · @srivatsav-kannan · AI agents

**Owns:** agent modules and prompts under `backend/app/agents/`, plus `backend/tests/test_no_price_limit_leak.py`.

**Phases**

- **T+0:00 – 0:15.** Read Appraisal, Inspection, Negotiation, Want, and PriceLimits. Forbidden keys: `buyer_max`, `seller_min`, `price_limits`. `access_token` only on want create.
- **T+0:15 – 1:00.**
  - [ ] `parse_want(text) -> WantCriteria`. Pull a budget out of the text into the server-only max, not into criteria.
  - [ ] `match_listings(criteria) -> list[Match]`.
  - [ ] Buyer and Seller agents and the negotiation protocol. Offers stay inside the limits. Limits are not in the return value.
  - [ ] `negotiate(...)` callable from hunt, target, and `POST /api/negotiations`.
  - [ ] Appraiser: comps plus `estimated_value`, `low`, `high`, `verdict` (global, not per user).
  - [ ] Inspector: `trust_level` and plain-language `signals` (global scam checks).
  - [ ] Lister: photo in, draft title / description / category / `suggested_price` out.
  - [ ] Prompts for those agents. One Grok seam each.
  - [ ] Leak test on negotiation and want read payloads and the OpenAPI schema.
- **T+1:00 – 1:30.** Replace stubs with Grok calls behind the same shapes. `GROK_API_KEY` from the environment only. Timeouts fall back to the stub.
- **T+1:30 – 1:50.** Prompt edits only if the feed is already up.
- **T+1:50 – 2:00.** Note for the README what the agents decide. No logs with limits or personal data.

**Handoffs.** Pure functions until tables exist. Gives @unclesdad stable badges and @heruirayli: `parse_want`, `match_listings`, `negotiate`, `appraise`, `inspect`, `draft_from_photo`.

## Person C · @heruirayli · Data, API, and ship

**Owns:** `backend/app/main.py`, models, SQLite, Scout, seed data, deploy config, `.env.example`, `.gitignore`, root README.

**Phases**

- **T+0:00 – 0:15.** Routers for the existing endpoints plus wants: `POST /api/wants`, `GET /api/wants/{id}`, `POST /api/wants/{id}/hunt`, `POST /api/wants/{id}/target`.
- **T+0:15 – 1:00.**
  - [ ] Schemas and SQLite for listings, wants, matches, negotiations, private limits, and tokens.
  - [ ] Seed about a dozen listings across bikes, computers, and furniture. `origin: "seed"`. Placeholder images. No real names, emails, or phone numbers.
  - [ ] All routes match the architecture doc, including the bot-facing want API. Bearer token on want reads, hunt, and target.
  - [ ] Scout pipeline: Scout → store → appraise → inspect for every listing. Public pages only, few pages, cache, stop on CAPTCHA or block. No live fetch required in the first hour.
  - [ ] `.env.example`: `GROK_API_KEY`, optional `GROK_API_BASE_URL`, optional `CORS_ORIGINS`. Empty values.
- **T+1:00 – 1:30.** Plug Person B's functions into the routes. Hunt runner calls match then negotiate for the top hits.
- **T+1:30 – 1:50.**
  - [ ] Serve `frontend/dist` from FastAPI.
  - [ ] Deploy as one public service. Laptop and phone. No login on the feed.
- **T+1:50 – 2:00.**
  - [ ] README sections filled.
  - [ ] Repo public.
  - [ ] Grok Bot session export with personal info removed.
  - [ ] Submission.

**Handoffs.** Publishes the base URL. Does not put limits or live tokens in `frontend/` or in committed examples. If Scout is blocked, ship seed data and say so.

## Integration checkpoints

| When | All three confirm |
| --- | --- |
| T+0:15 | Contract frozen, including want routes. |
| T+1:00 | Feed shows both badges. Lister and negotiation respond. Want create returns a token. Leak test passes. |
| T+1:30 | One URL loads the feed. Hunt or target returns matches and an outcome. |
| T+2:00 | README complete, repo public, session export cleaned, link submitted. |
