# Brief: Person C, data, API, and ship

> Kickoff brief for one teammate's Grok Bot, kept as a record of how the work was split.

Fairlot is an AI-run classifieds board for SF Bay Area bikes, computers, and furniture (Berkeley x Stanford Grok Bot Hackathon, Best Design, about two hours). This server stores listings, wants, matches, negotiations, and private ceilings, and it runs Scout, the hunt runner, and the HTTP API a user's Grok Bot calls. Negotiation stays on the server so ceilings stay private.

**Owner:** @heruirayli. **Role:** schema, database, routes, Scout, deploy, README, submission.

## You work in

- `backend/app/main.py`, `routes.py`, `schemas.py`, `db.py`, `repository.py`, `services.py`, `runner.py`, `seed.py`
- `backend/app/agents/scout.py`
- `backend/tests/test_smoke.py`
- `Dockerfile`, `.env.example`, `.gitignore`, `README.md`
- [GROKBOT_INTEGRATION.md](../../architecture/GROKBOT_INTEGRATION.md) (keep it true to the live JSON)

## Do not edit

`backend/app/agents/buyer.py`, `negotiator.py`, `appraiser.py`, `inspector.py`, `lister.py`, `llm.py` (@srivatsav-kannan). `backend/tests/test_no_price_limit_leak.py` (same). `frontend/` (@unclesdad). Ask instead of changing an agent signature.

## Contract you must honor

[ARCHITECTURE.md](../../architecture/ARCHITECTURE.md) is the product contract. [INTEGRATION.md](../../architecture/INTEGRATION.md) is the call graph. `backend/app/schemas.py` is the JSON.

Public routes already wired:

`GET /api/listings`, `GET /api/listings/{id}`, `POST /api/lister`, `POST /api/listings`, `POST /api/negotiations`, `GET /api/negotiations/{id}`, `POST /api/scout/run`, `POST /api/wants`, `GET /api/wants/{id}`, `POST /api/wants/{id}/hunt`, `POST /api/wants/{id}/target`.

Scout pipeline you own: `scout_run` → insert listing → `appraise` → `inspect`. Rules in the scout module: public pages only, `MAX_PAGES_PER_RUN` (3), no sign-in, posting, messaging, or accounts, cache, and on a CAPTCHA or block raise `ScoutStopped` and return `stopped: true`. Do not work around the challenge. The stub does not fetch.

`runner.run_hunt(want_id)` and `run_target(want_id, listing_id)` are the job seam. They run inline. A queue can replace the body later.

`get_want` selects public columns only. `get_want_max` and `get_token_hash` are separate and must stay out of response models and logs. FastAPI serves `frontend/dist` when the folder exists and still boots when it does not.

## Your tasks

1. **Now.** `python -m pytest backend/tests -q`. Read `routes.py`, `services.py`, `runner.py`, and `agents/scout.py`.
2. **T+0:15 – 1:00.** Replace the Scout stub with a polite fetcher that obeys the rules above. Keep seed rows (`origin: "seed"`) if a category comes back empty. Confirm new rows are appraised and inspected before they are readable.
3. **T+1:00 – 1:30.** After @srivatsav-kannan lands real `complete()` calls, the routes should still be the ones in the table. Update [GROKBOT_INTEGRATION.md](../../architecture/GROKBOT_INTEGRATION.md) if a JSON field changes (it should not, without all three).
4. **T+1:30 – 1:50.** One public HTTPS URL. Laptop and phone. No login. Mount or copy `frontend/dist` from @unclesdad.
5. **T+1:50 – 2:00.** Fill the README, make the repo public, add a Grok Bot session export with personal info removed, submit.

## Run and verify

```bash
pip install -r backend/requirements.txt
python -m pytest backend/tests -q
uvicorn backend.app.main:app --port 8000
```

Smoke and leak tests must pass before you push. `POST /api/wants` then hunt with `Authorization: Bearer` must return matches and transcripts and must not return the ceiling.

Production image:

```bash
docker build -t fairlot . && docker run --rm -p 8000:8000 fairlot
```

When a frontend build exists, mount it: `-v "$PWD/frontend/dist:/app/frontend/dist:ro"`.

## Branch and PR

`c/<feature>`, small PRs into `main`. Never force-push `main`.

## Rules for any AI on this repo

No secrets, keys, real names, emails, or phone numbers. `GROK_API_KEY` from the environment only. Ceilings and token hashes never appear in API responses (the raw token is returned once from create), logs, or the frontend bundle. Scout stays on public pages, a few per run, and stops on a block.

## Done

The endpoints above match [ARCHITECTURE.md](../../architecture/ARCHITECTURE.md) and [GROKBOT_INTEGRATION.md](../../architecture/GROKBOT_INTEGRATION.md), Scout either fetches politely or reports why it stopped, the process serves `frontend/dist` when present, and the public link works without an account.

You own T+1:30 (deployed) and T+2:00 (README, public repo, cleaned session export, submission).
