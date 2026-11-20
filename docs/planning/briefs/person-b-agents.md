# Brief: Person B, AI agents

> Kickoff brief for one teammate's Grok Bot, kept as a record of how the work was split.

Fairlot is an AI-run classifieds board for SF Bay Area bikes, computers, and furniture (Berkeley x Stanford Grok Bot Hackathon, Best Design, about two hours). Site-run agents on this server price every listing, check it for scams, write a listing from a photo, and negotiate for a want inside ceilings only the server knows. A user's own Grok Bot is only a client.

**Owner:** @srivatsav-kannan. **Role:** the agent decisions and the leak test.

## You work in

- `backend/app/agents/buyer.py` — `parse_want`, `match_listings`, `private_max_from_text`
- `backend/app/agents/negotiator.py` — `negotiate` (Buyer and Seller)
- `backend/app/agents/appraiser.py` — `appraise`
- `backend/app/agents/inspector.py` — `inspect` (global, every listing)
- `backend/app/agents/lister.py` — `draft_from_photo`
- `backend/app/agents/llm.py` — `complete`
- `backend/tests/test_no_price_limit_leak.py`

## Do not edit

`backend/app/agents/scout.py` (@heruirayli). `backend/app/routes.py`, `schemas.py`, `db.py`, `repository.py`, `services.py`, `runner.py`, `seed.py`, `main.py`. `frontend/` (@unclesdad). [GROKBOT_INTEGRATION.md](../../architecture/GROKBOT_INTEGRATION.md). Ask the owner instead of changing a signature.

## Contract you must honor

Signatures and return types are in [INTEGRATION.md](../../architecture/INTEGRATION.md). HTTP models are `backend/app/schemas.py`.

```text
parse_want(text: str) -> WantCriteria
match_listings(criteria: WantCriteria) -> list[Match]
negotiate(listing: ListingRecord, buyer_max: int, seller_min: int) -> NegotiationDraft
appraise(listing: ListingRecord) -> Appraisal
inspect(listing: ListingRecord, appraisal: Appraisal) -> Inspection
draft_from_photo(photo: bytes, filename: str | None = None) -> Draft
complete(prompt: str, *, image: bytes | None = None, timeout_s: float = 8.0) -> str | None
```

`WantCriteria` is category, area, keywords. It must not grow a price field. `NegotiationDraft` is outcome plus messages. Verdict is `good_deal` if ask < low, `fair` inside `[low, high]`, `overpriced` above high. Trust is `high` | `medium` | `low`.

`private_max_from_text` may return an int. The service stores it. You must not put that int on a model the service returns, and you must not log it. `negotiate` may use the two ints to pick offers. Offers stay inside the overlap when there is one. Message text must not name the bounds. `complete()` prompts must not include them.

If `complete()` returns `None`, call the existing `stub_*` function so the page still works.

## Your tasks

1. **Now.** Run `python -m pytest backend/tests/test_no_price_limit_leak.py -q`. Read `stub_parse_want`, `stub_match_listings`, `stub_negotiate`, `stub_appraise`, and `stub_inspect`.
2. **T+0:15 – 1:00.** Improve those decisions. Keep signatures. Inspector stays global (it does not take a user id). Lister still returns category, title, description, suggested price.
3. **T+1:00 – 1:30.** Implement `complete()` with `GROK_API_KEY` and optional `GROK_API_BASE_URL`. Timeouts and missing keys return `None`.
4. **T+1:30 – 2:00.** Prompt tweaks only after feed and hunt work. Tell @heruirayli what the agents decide, with no ceilings in the note.

## Run and verify

```bash
pip install -r backend/requirements.txt
python -m pytest backend/tests/test_no_price_limit_leak.py backend/tests/test_smoke.py -q
```

Both files must pass before you push. The leak test fails if a response or an OpenAPI example carries `buyer_max`, `seller_min`, `price_limits`, `max_price`, or a want token except the one `access_token` on create.

## Branch and PR

`b/<feature>`, small PRs into `main`. Never force-push `main`.

## Rules for any AI on this repo

No secrets, keys, real names, emails, or phone numbers in commits. Keys from the environment only. Ceilings never leave the server. Scout (not your file) reads public pages only, a few per run, no sign-in, posting, messaging, or accounts, and stops on a CAPTCHA or block.

## Done

The functions above still match [INTEGRATION.md](../../architecture/INTEGRATION.md), hunt and negotiate return only public transcripts, the leak test passes, and a missing key still serves stub results.

You own the T+1:00 agent checkpoint: live model or a clean stub fallback, with the leak test green.
