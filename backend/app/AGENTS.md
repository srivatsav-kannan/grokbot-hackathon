# backend/app — Person C

You are in @heruirayli's area: routes, schemas, SQLite, services, the hunt runner, seed data, and `main.py`. Read `docs/planning/briefs/person-c-data-api-ship.md` and `docs/architecture/INTEGRATION.md` first.

`agents/scout.py` is also yours. Every other file under `agents/` belongs to @srivatsav-kannan. Do not change those function signatures. Do not edit `frontend/` (@unclesdad) or `backend/tests/test_no_price_limit_leak.py`.

Private ceilings and token hashes stay in the database and in `get_want_max` / `get_token_hash`. Do not add them to a Pydantic response. Scout: public pages only, a few per run, no accounts, stop on a CAPTCHA or block.
