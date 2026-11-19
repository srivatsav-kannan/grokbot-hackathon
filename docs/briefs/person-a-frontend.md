# Brief — Person A, frontend and design

Fairlot is an AI-run classifieds board for SF Bay Area bikes, computers, and furniture (Berkeley x Stanford Grok Bot Hackathon, Best Design, about two hours). Every listing shows up already priced and checked. A buyer agent can hunt for what someone wants and negotiate inside a ceiling that never reaches the browser.

**Owner:** @unclesdad. **Role:** visual system and the screens.

## You work in

`frontend/` only. Vite, React, TypeScript. Read `docs/INTEGRATION.md` and `GET /openapi.json` on the API (default `http://localhost:8000/openapi.json`). Hand-write the client types to match `backend/app/schemas.py`, or generate them. Do not invent fields.

## Do not edit

`backend/`, `docs/GROKBOT_INTEGRATION.md`, agent files, seed data. Ask @heruirayli for API changes and @srivatsav-kannan for badge meanings. This plumbing branch intentionally has no `frontend/` files so it does not collide with you.

## Contract you must honor

Frozen names and enums are in `docs/INTEGRATION.md`.

Feed and listing:

- `GET /api/listings?category=&q=` cards with `appraisal.verdict` and `inspection.trust_level`
- `GET /api/listings/{id}` adds description, comps, and signals
- `POST /api/lister` multipart field `photo` → `{ draft }`
- `POST /api/listings` publishes the edited draft and returns the detail
- `POST /api/negotiations` body `{ "listing_id" }` and `GET /api/negotiations/{id}` return the transcript only

Wants, after the feed looks right. Do not block badges on these.

- `POST /api/wants` → `{ id, access_token }` once. Keep the token in memory for that session.
- `GET /api/wants/{id}`, `POST /api/wants/{id}/hunt`, `POST /api/wants/{id}/target` send `Authorization: Bearer <access_token>`.
- Show criteria, match cards with the same badges, and the transcript. There is no max-price or seller-floor field. Do not add an input for one.

`VITE_API_BASE_URL` empty means same origin. For local Vite, set it to `http://localhost:8000` or proxy `/api`.

## Your tasks

Priority order. Timing is from the start of the build.

1. **Now.** Photo-first feed: type, color, spacing, category chips, cards with price and trust badges, Sample mark when `origin` is `seed`. Phone width and laptop width.
2. Listing detail with comps, signal sentences, and one primary action: Make an offer.
3. Sell with a photo: upload, edit the draft, publish, land on the new listing.
4. Negotiation view: messages and deal / no deal. No ceiling controls.
5. **T+1:00.** Drop any mock that disagrees with the live API.
6. **T+1:30.** Polish, empty and error states, phone pass.
7. **After the feed.** Want screens for the endpoints above.
8. **T+1:50.** Notes or screenshots for @heruirayli (desktop feed, phone feed, one flow).

## Run and verify

API, from the repo root:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --port 8000
```

`GET http://localhost:8000/api/listings` should return 12 seed rows with both badges. Your app should do the same on a narrow viewport. You do not have to run the Python tests before a frontend-only push. Do not merge a client that sends `buyer_max`, `seller_min`, or `max_price` except the single optional `max_price` on create-want, and never display that number after create.

## Branch and PR

`a/<feature>`, small PRs into `main`. Never force-push `main`.

## Rules for any AI on this repo

No secrets, keys, real names, emails, or phone numbers in the repo. Keys stay in env vars. Price limits never leave the server. Scout reads public pages only, a few per run, no sign-in, posting, messaging, or accounts, and stops on a CAPTCHA or block. No login wall.

## Done

The feed is obvious on a phone and a laptop, badges are the verdict and the trust check, sell-from-photo and the transcript work against the live API, and you have not edited the backend.

You are accountable for the T+1:00 feed checkpoint and the T+1:30 phone pass. Hunt UI is after that, not instead of it.
