# Fairlot — notes for coding agents

Photo-first classifieds for SF Bay Area bikes, computers, and furniture. Server-side agents price, check, list, and negotiate. A user's Grok Bot is a client of the wants API. Read the brief for the person you are helping before editing.

| Path | Person | Brief |
| --- | --- | --- |
| `frontend/` | @unclesdad | `docs/briefs/person-a-frontend.md` |
| `backend/app/agents/` except `scout.py` | @srivatsav-kannan | `docs/briefs/person-b-agents.md` |
| `backend/tests/test_no_price_limit_leak.py` | @srivatsav-kannan | `docs/briefs/person-b-agents.md` |
| `backend/app/` routes, schema, db, repository, services, runner, seed, `main.py` | @heruirayli | `docs/briefs/person-c-data-api-ship.md` |
| `backend/app/agents/scout.py` | @heruirayli | `docs/briefs/person-c-data-api-ship.md` |
| `docs/GROKBOT_INTEGRATION.md`, `Dockerfile`, `README.md` | @heruirayli | `docs/briefs/person-c-data-api-ship.md` |

Product contract: `docs/ARCHITECTURE.md`. Call graph: `docs/INTEGRATION.md`. Bot recipe: `docs/GROKBOT_INTEGRATION.md`.

## Rules

- Do not commit secrets, keys, real names, emails, or phone numbers. API keys come from environment variables only.
- Buyer ceilings and seller floors never leave the server. They are not response fields, logs, or frontend code. `access_token` is returned once from `POST /api/wants`.
- Scout reads public pages only, a few pages per run, with no sign-in, posting, messaging, or accounts. On a CAPTCHA or block it stops and reports. It does not work around the challenge.
- Small branches (`a/…`, `b/…`, `c/…`) and PRs into `main`. Never force-push `main`.
- If you are about to edit a path in another row of the table, stop and ask that owner.
