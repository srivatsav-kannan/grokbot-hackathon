# backend/app/agents — Person B, except Scout

@srivatsav-kannan owns `buyer.py`, `negotiator.py`, `appraiser.py`, `inspector.py`, `lister.py`, and `llm.py`. Read `docs/planning/briefs/person-b-agents.md` before changing a function. Keep the signatures in `docs/architecture/INTEGRATION.md`.

`scout.py` belongs to @heruirayli. Do not edit it, and do not edit `../routes.py`, `../schemas.py`, `../services.py`, `../repository.py`, or anything under `frontend/`.

`parse_want` must not return a ceiling. `negotiate` must not return the bounds it was given. `complete()` calls the Anthropic Messages API with `ANTHROPIC_API_KEY` and returns `None` on failure so the stub still runs. Optional `ANTHROPIC_MODEL` overrides the default Claude Sonnet model. Do not log ceilings, tokens, or the API key.
