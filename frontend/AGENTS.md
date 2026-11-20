# Frontend notes

You are in @unclesdad's area. Read [DESIGN.md](DESIGN.md) before changing the look, and `docs/planning/briefs/person-a-frontend.md` before changing behavior.

- Work only under `frontend/`.
- Types in `src/types.ts` mirror `backend/app/schemas.py`. If the server adds a field, update both in the same change with the API owner.
- `src/api/client.ts` is the only module that talks to `/api`.
- `VITE_API_BASE_URL` empty means same origin. Development proxies `/api` and `/placeholders` to port 8000.
- Price limits never appear in this tree. The want token is stored by `src/lib/session.ts` and is not rendered.
- Badge words stay "Good deal", "Fair", "Overpriced", "High trust", "Medium trust", "Low trust". Seed rows say "Sample".
- Motion has to bail out when `prefers-reduced-motion: reduce` is set. See DESIGN.md.
