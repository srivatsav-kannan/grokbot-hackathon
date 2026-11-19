# Fairlot frontend

Person A owns this folder. The visual system is in [DESIGN.md](DESIGN.md). The HTTP shapes are `backend/app/schemas.py`. Do not invent fields.

## Run it

From the repo root, start the API:

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --port 8000
```

In another shell:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` and `/placeholders` to http://127.0.0.1:8000. Leave `VITE_API_BASE_URL` empty for that. Set it only when the API is on another origin (the API allows `http://localhost:5173` via `CORS_ORIGINS`).

`npm run build` writes `frontend/dist`. From the repo root, the same uvicorn process serves that folder and `/api` on port 8000. The Docker image does not copy the UI; mount the build:

```bash
docker build -t fairlot .
docker run --rm -p 8000:8000 -v "$PWD/frontend/dist:/app/frontend/dist:ro" fairlot
```

## Data

There is no mock catalog in this folder. Listings, drafts, and transcripts come from the API. An empty list, a missing listing, and a down API each have their own screen. Home with no rows says "Listings coming soon".

## Do not

- Send or render `buyer_max`, `seller_min`, `price_limits`, or `max_price`.
- Put `access_token` in the URL, the visible page, or a form field. `src/lib/session.ts` keeps it in `sessionStorage` for the tab that created the want.
- Edit `backend/`.
