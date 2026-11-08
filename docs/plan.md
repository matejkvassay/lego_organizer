# Plan: Lego Organizer v1

> The original plan, agreed with the owner in a structured interview (see [How this was built](../README.md#how-this-was-built))
> before any code was written. It is kept as a record of intent; the section at the bottom lists where the
> implementation deliberately differs. For how the system actually works, read [architecture.md](architecture.md).

## What it does
- Catalog ~200 Lego sets and other items. Each item sits in a storage box, a free-text ID like `587B`.
- Find things by browsing themes, searching the collection, or looking up a box.

## Stack
- **Backend**: Python, FastAPI, SQLite (FTS5 for search), SQLAlchemy (Postgres move stays possible).
- **Frontend**: React, Vite, TypeScript, Tailwind.
- **Packaging**: one Docker image where FastAPI serves the built frontend, plus Docker Compose for local runs. Cloud Run-ready, but no deploy work now.
- **Config**: all settings from `.env`, with a committed `.env.example`.

## Auth
- Real Google OAuth login; only the email in `ALLOWED_EMAIL` gets in. Works on localhost.
- Needs a Google OAuth client (ID + secret), created once.
- No auth bypass: login is always on (decided after Google login worked locally).

## Data model
- **Item**: `type` (set | other), `box` (string), `notes`, tags, `added_at`.
  - set: link to cached Brickset record.
  - other: `title`, `description`, no image.
- **Cached Brickset set**: number, name, theme, subtheme, year, pieces, minifigs, image URL (hotlinked), raw payload. Fetched once, then served from cache.
- **Tag**: many-to-many with items, created as you type.
- Duplicates: owning a set twice = two items. No quantity or condition fields.

## Add a set
- **AI mode (default)**: user types/speaks a description. A PydanticAI agent (OpenAI Luna model, no reasoning) has one tool: Brickset search. Up to `AGENT_MAX_STEPS` searches (default 3). Returns structured ranked candidates (number, name, image). User picks one, then enters box, tags, notes.
- **Keyword mode**: toggle turns off AI, queries Brickset directly.
- **Voice**: mic button records in browser, sends audio to OpenAI Whisper; transcript fills the search bar.
- Agent model, transcription model and loop limit are env vars. Look up exact OpenAI model IDs at build time.
- Brickset rate limits: cache every lookup, cap agent calls, never refetch unless asked.

## Browse and find
- **Drill-down**: Theme -> Subtheme -> sets (BrickLink style). Tags and Boxes are separate entry points.
- **Collection search**: plain BM25 (SQLite FTS5) over name, number, theme, tags, box, notes. No AI.
- **Views**: image grid with table toggle.
- **Detail page**: edit box, tags, notes; delete item.
- **Other items**: quick-add form; shown in same lists and searchable.

## Also in v1
- Export: JSON and CSV download.
- Seed command: a few example sets (2015 Death Star, recent Millennium Falcon, a Harry Potter set, a Ninjago set), deletable in the app.
- Tests: backend data layer and add flow, with Brickset and OpenAI mocked.

## Out of scope
- Cloud Run deploy, Litestream, image download, barcode scanning, price tracking, parts/minifig inventories, manuals, multi-user.

## User must provide
1. Brickset API key.
2. OpenAI API key.
3. Google OAuth client ID + secret, and allowed email.

Build with stubs until these are available.

## Where the implementation differs from this plan
- **No Alembic yet.** Tables are created on startup (`create_all`). Add migrations before the first schema change that must preserve data.
- **Richer agent tool.** After trying real descriptions, the Brickset search tool also accepts `theme`, `subtheme` and `year` filters, not just keywords. Remembered names are often not the official title, and filters let the model reason from its Lego knowledge ("90s pharaoh sets are theme Adventurers").
- **Agent model** is `gpt-6-luna` (the ID the owner's OpenAI project exposes), with reasoning set to `none`; both are env settings.
- **No auth bypass.** The planned `AUTH_DISABLED` switch was removed once Google login worked locally, so there is only one code path.
- **Unverified at time of writing:** the Docker image build, and the default `TRANSCRIBE_MODEL` (`gpt-4o-transcribe`).

