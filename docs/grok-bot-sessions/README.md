# Grok Bot session exports

Each teammate drove their part of Fairlot through their own Grok Bot on November 19, 2026, during the Berkeley x Stanford Grok Bot Hackathon. These files are the cleaned exports of those three sessions, one per person. They keep the user-visible messages in order and leave out hidden prompts and internal tool calls.

| File | Whose session | Track | What it covers |
| --- | --- | --- | --- |
| [person-a-frontend.md](person-a-frontend.md) | Charlie Kerr (@unclesdad) | Person A, frontend and design | Design research, a Cursor cloud agent building the Vite, React, and TypeScript frontend, a local preview with screenshots, and the merges of PR #6 and PR #8. |
| [person-b-agents.md](person-b-agents.md) | Srivatsav Kannan (@srivatsav-kannan) | Person B, AI agents | The kickoff architecture, roadmap, and task split, the Render deploy, the switch to Claude models, the move from SQLite on `/tmp` to Postgres, and the Deals core loop. |
| [person-c-data-api-ship.md](person-c-data-api-ship.md) | Ray Li (@heruirayli) | Person C, data, API, and ship | Repo setup, the live Scout fetcher (PR #2), README work (PR #3 and PR #9), multi-round negotiation (PR #10), live checks, and the pitch deck handoff. |

## How the exports were cleaned

The Tracks Guide asks for the session export with personal information removed. The exports contain no email addresses, phone numbers, API keys, access tokens, database URLs, or Render secrets. GitHub handles that already appear in this public repo are kept so the story can be followed. Two edits were made when the exports were moved into this folder:

- In `person-a-frontend.md`, a link to a private Cursor agent page was replaced with `[Cursor agent link removed]`.
- In `person-b-agents.md`, the name of an unrelated private project that shares the Postgres server was replaced with `[another project's]`.

The rest of the text is as each teammate's Grok Bot exported it. Paths such as `docs/ROADMAP.md` inside the exports refer to the flat `docs/` layout from the day of the build. Those files now live in [`../planning/`](../planning/) and [`../architecture/`](../architecture/).
