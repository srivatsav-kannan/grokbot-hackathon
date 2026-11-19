# backend/app/agents — Person B, except Scout

@srivatsav-kannan owns `buyer.py`, `negotiator.py`, `appraiser.py`, `inspector.py`, `lister.py`, and `llm.py`. Read `docs/briefs/person-b-agents.md` before changing a function. Keep the signatures in `docs/INTEGRATION.md`.

`scout.py` belongs to @heruirayli. Do not edit it, and do not edit `../routes.py`, `../schemas.py`, `../services.py`, `../repository.py`, or anything under `frontend/`.

`parse_want` must not return a ceiling. `negotiate` must not return the bounds it was given. `complete()` reads `GROK_API_KEY` from the environment and returns `None` on failure so the stub still runs. Do not log ceilings or tokens.
