# Grok Bot session: Person B, AI agents (@srivatsav-kannan)

Full Grok Bot session from the teammate who owned AI agents. Personal info (names, emails, phone numbers, API keys, tokens) removed. Nov 19, 2026, America/Los_Angeles.

### Kickoff

**Owner:** We're at the Berkeley × Stanford Grok Bot Hackathon, Best Design track. Rebuild Craigslist for the SF Bay Area (bikes, computers, furniture) so Grok Bots do the work: Scout, Appraiser, Inspector, Lister, Buyer and Seller agents. Rules: read public pages only; never sign in, post, message, buy, or create accounts; keep volume low; stop on CAPTCHA/blocks; never put names, emails, phones, keys, or tokens in replies. Repo: `https://github.com/[handle]/grokbot-hackathon`.

**Grok Bot:** Saved the project and rules. Connected to the empty private repo and prepared to scaffold.

**Owner:** Shared the tracks guide PDF for reference.

**Grok Bot:** Read the guide. Best Design needs a deployed public link (no login wall, laptop + phone), a public GitHub repo with README and Grok Bot session export (personal info removed), and the nine README sections.

### Plan first

**Owner:** Wait. First give me a whole roadmap and architecture and push it to GitHub. Split tasks between the three of us.

**Grok Bot:** Stopped the code scaffold. Pushed `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/TASKS.md`, and a README stub to `main` via a Cursor cloud agent. Split: Person A frontend, Person B agents, Person C data/API/ship.

**Owner:** Assigned roles (Person A = Team member A / frontend; Person B = [owner] / agents; Person C = Team member C / data, API, ship).

### Product direction

**Owner:** A user types what they want (native Grok Bot integration). Bots find sellers and negotiate. The user can also point a buyer bot at a listing. Scam checks run globally, not per user. Clarified how the bot runs inside the app.

**Grok Bot:** Updated docs: wants + hunting buyer agents; Scout/Appraiser/Inspector stay global; private max never leaves the server; a user's own Grok Bot is only a client of the public wants API. Cut order: feed + badges → wants + hunt → Grok Bot integration demo.

### Deploy as we go

**Owner:** Build all this and start deployment. Deploy as we go on Render. Keep it alive by pinging. Spawn parallel subagents.

**Grok Bot:** Launched parallel Cursor cloud agents for deploy plumbing (Dockerfile, `render.yaml`, `/api/health`, GitHub Actions keepalive every 10 minutes), Claude-backed agents (no Grok API credits), and the main product build. Live site: `https://fairlot.onrender.com`.

**Owner:** Switch to Claude as the agent; we don't have Grok API credits. Later: Opus 5.5 on low for negotiation messages; Sonnet 5.5 for scam Inspector; Haiku as default. Paste the key into Render as `ANTHROPIC_API_KEY`.

**Grok Bot:** Wired `complete()` to Anthropic with those model overrides and env vars. Documented how to set the key in Render (never commit it).

### AI-native marketplace

**Owner:** Buyer and seller both AI-native. Background loop finds new sellers; users can list. Scout aggregates other marketplaces with scam detection. Prefer native listings; for external ones tell the user what to do (suggested offer + copyable message). Add email/password auth. Push frontend to Render. No PRs — merge all outstanding ones.

**Grok Bot:** Merged open PRs into `main`. Added auth, background scout cycle, multi-marketplace scout (Craigslist live; others blocked by 403/login), and frontend wiring. Set `SCOUT_LIVE=1` on Render.

**Owner:** No sample labels. Search shows a few listings then an option to fire a persistent buyer bot. Clean place for buyer bots and seller bots, with notifications. Listings are AI-native. If search is empty, run Scout (demo). Use something not too expensive for models.

**Grok Bot:** Steered the build: buyer-bot card on search, Deals hub for bots, on-empty-search scout, private min/max next to the offer box, human vs bot-negotiates toggle, Opus for messages / Sonnet for Inspector / Haiku default.

### Hardening the core loop

**Owner:** The Huffy bike is not Craigslist — it was a demo. Verify real Craigslist is in. Everything must be fully usable, idempotent, and have one path per workflow. Wrap it up and make all the workflows come alive.

**Owner:** Sell-from-photo / login UX is bad. Logout is in the middle. No clarity. Sell is highlighted wrong. Accounts get blocked. Agent chat is bad. Want chatboxes. Send-buyer-agent and Make-an-offer are broken. No sale idempotency, no completion record, no storage.

**Grok Bot:** Found root cause: SQLite on `/tmp` wiped on every free-tier restart/deploy. Steered the build to: Postgres via `DATABASE_URL` with schema `fairlot` only (shared free DB, separate from another project); fix make-offer and send-buyer-bot with Idempotency-Key; one immutable sale/completion record that marks the listing sold; Deals as a messaging UI (conversation list + chat bubbles + composer); clean header (Log out in account menu).

**Owner:** Use the existing free [another project's] Postgres with a separate fairlot schema. Then: time is almost up — just do core functionality and fix the UI.

**Grok Bot:** Asked [owner] to paste the Internal Database URL into Fairlot's `DATABASE_URL` on Render (password not readable via API). Cut scope to core loop + UI. After the push landed, live checks showed:
- `GET /api/health` → `{"ok": true, "database": "postgres"}`
- `/login`, `/signup`, `/deals` return 200 and the SPA
- Signup survives redeploy
- Offer with same Idempotency-Key returns the same thread
- Accept creates one sale (`sold_for`) and a second accept is a no-op
- Buyer bot from search appears in Deals immediately

**Owner:** Pause all agents.

**Grok Bot:** Cancelled the running cloud agent and background watchers. Confirmed the core fixes already on `https://fairlot.onrender.com`.

### Session export

**Owner:** Upload Grok Bot history to GitHub the way the tracks guide requires. Put it in the README.

**Grok Bot:** Guide requires the full session export with personal info removed in the public repo (and README with the nine sections). Appended this cleaned Person B export to `README.md` (Team member C's export already present). Repo still needs to be made public before final submission.

### How Grok Bot helped (Person B)

- Wrote and pushed architecture, roadmap, and task split at kickoff.
- Launched and steered Cursor cloud agents for scaffold, agents, Scout, Render deploy, and the core loop.
- Wired Claude models (Haiku / Opus messages / Sonnet Inspector) and private-limit leak rules.
- Diagnosed wiped accounts (`/tmp` SQLite) and moved Fairlot to Postgres schema `fairlot`.
- Drove the final core path: auth → browse → make offer → chat → accept → one completion record; plus buyer bots in Deals and a chat-first Deals UI.
