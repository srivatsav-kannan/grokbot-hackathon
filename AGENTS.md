# Fairlot — notes for coding agents

Photo-first classifieds for SF Bay Area bikes, computers, and furniture. Server-side agents price, check, list, and negotiate. A user's Grok Bot is a client of the wants API. Read the brief for the person you are helping before editing.

| Path | Person | Brief |
| --- | --- | --- |
| `frontend/` | @unclesdad | `docs/planning/briefs/person-a-frontend.md` |
| `backend/app/agents/` except `scout.py` | @srivatsav-kannan | `docs/planning/briefs/person-b-agents.md` |
| `backend/tests/test_no_price_limit_leak.py` | @srivatsav-kannan | `docs/planning/briefs/person-b-agents.md` |
| `backend/app/` routes, schema, db, repository, services, runner, seed, `main.py` | @heruirayli | `docs/planning/briefs/person-c-data-api-ship.md` |
| `backend/app/agents/scout.py` | @heruirayli | `docs/planning/briefs/person-c-data-api-ship.md` |
| `docs/architecture/GROKBOT_INTEGRATION.md`, `Dockerfile`, `README.md` | @heruirayli | `docs/planning/briefs/person-c-data-api-ship.md` |

Product contract: `docs/architecture/ARCHITECTURE.md`. Call graph: `docs/architecture/INTEGRATION.md`. Bot recipe: `docs/architecture/GROKBOT_INTEGRATION.md`.

## Rules

- Do not commit secrets, keys, real names, emails, or phone numbers. API keys come from environment variables only.
- Buyer ceilings and seller floors never leave the server. They are not response fields, logs, or frontend code. `access_token` is returned once from `POST /api/wants`.
- Scout reads public pages only, a few pages per run, with no sign-in, posting, messaging, or accounts. On a CAPTCHA or block it stops and reports. It does not work around the challenge.
- Small branches (`a/…`, `b/…`, `c/…`) and PRs into `main`. Never force-push `main`.
- If you are about to edit a path in another row of the table, stop and ask that owner.
