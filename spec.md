# FitLab — Architecture Specification

**Status:** Design (Week 5 deliverable)
**Date:** 2026-10-25
**Scope:** Formal specification for every component in `plan.md`: app server, database, weather, generator, critique, front end.
**Inputs:** `intent/*.md` (7 approved intent documents), `plan.md`, `team-project-1.md`.
**Contents of this document:** for each component — what it does, its **language** decision with the alternative considered, its **model** decision with the alternative considered, its interfaces, its dependencies with reasons, its numbered behaviors, and its failure handling. Section 7 defines the critique JSON contract exactly, because the automated tests assert against it. Section 8 is a consolidated failure matrix, Section 9 is the cost estimate, Section 10 is the traceability matrix from intent to code to test.

**No code is written in this document.** Interface descriptions are signatures and payload shapes only.

---

## 1. Model slug verification (prerequisite for Section 3)

Every model slug named in `plan.md`, `intent/*.md`, or the team brief was checked against the live OpenRouter catalog on **2026-10-25**, retrieved with `GET https://openrouter.ai/api/v1/models` (**467 models** at time of check). The catalog was fetched directly with `curl`; the values below are read from that JSON, not from memory or from a model listing page.

### 1.1 Slugs that still exist

| Slug | Name | In modalities | Out modalities | Context | Prompt $/Mtok | Completion $/Mtok | Verdict |
|---|---|---|---|---|---|---|---|
| `xiaomi/mimo-v2.6-flash` | Xiaomi: MiMo-V2.6-Flash | text, image, video, audio | text | 1,050,000 | 0.14 | 0.28 | **Usable — cheap critique model** |
| `minimax/minimax-m3` | MiniMax: MiniMax M3 | text, image, video | text | 1,048,576 | 0.30 | 1.20 | **Usable — strong critique model** |
| `openai/gpt-4o-mini` | OpenAI: GPT-4o-mini | text, image, file | text | 128,000 | 0.15 | 0.60 | Exists — the cheap model named in `plan.md` |
| `minimax/minimax-01` | MiniMax: MiniMax-01 | text, image | text | 1,000,192 | 0.20 | 1.10 | Exists — the model named in `plan.md`, now superseded by `minimax-m3` |
| `minimax/minimax-m3.1-flash` | MiniMax: MiniMax M3.1 Flash | text, image, video | text | — | — | — | Exists — **rejected**: `reasoning.mandatory = true`, so reasoning cannot be switched off |

### 1.2 Slugs that no longer exist — these are flagged and must not be used

| Slug | Where it came from | Status on 2026-10-25 | Replacement chosen in this spec |
|---|---|---|---|
| `black-forest-labs/flux-1-schnell` | `plan.md` → `generator.py` row | **GONE.** No OpenRouter model ID contains `flux` | `google/gemini-3.1-flash-image` |
| `recraft/recraft-v3` | `plan.md` → `generator.py` row | **GONE.** No OpenRouter model ID contains `recraft` | `google/gemini-3.1-flash-image` |
| `anthropic/claude-3.5-sonnet` | `plan.md` → Proof section, frontier-vision eval | **GONE** | `minimax/minimax-m3` (strong) |
| `google/gemini-pro-vision` | `plan.md` → Proof section, frontier-vision eval | **GONE** | `minimax/minimax-m3` (strong) |

A catalog-wide scan for `flux`, `stable-diffusion`, `sdxl`, `dall-e`, `dalle`, `ideogram`, `recraft`, `imagen`, `qwen-image`, and `seedream` returned **zero** matching model IDs. The open-weight diffusion providers that `plan.md` assumed are no longer reachable through OpenRouter at all.

### 1.3 What OpenRouter can still generate images

Every model whose `architecture.output_modalities` includes `image` (complete list from the same catalog fetch):

| Slug | Display name | In | Out | Prompt $/Mtok | Completion $/Mtok | `image_output` rate |
|---|---|---|---|---|---|---|
| `google/gemini-3-pro-image` | Nano Banana Pro | image, text | image, text | 2.00 | 12.00 | 0.00012 |
| `google/gemini-nano-banana-2.1` | Nano Banana 2.1 | image, text | image, text | 1.50 | 7.50 | 0.00003 |
| `openai/gpt-5-image` | GPT-5 Image | image, text, file | image, text | 10.00 | 10.00 | 0.000008 |
| `openai/gpt-5.4-image-2` | GPT-5.4 Image 2 | image, text, file | image, text | 8.00 | 15.00 | 0.000008 |
| `openai/gpt-5-image-mini` | GPT-5 Image Mini | file, image, text | image, text | 2.50 | 2.00 | 0.000008 |
| `google/gemini-3.1-flash-image` | Nano Banana 2 | image, text | image, text | 0.50 | 3.00 | 0.00006 |
| `google/gemini-3.1-flash-image-preview` | Nano Banana 2 (preview) | image, text | image, text | 0.50 | 3.00 | 0.00006 |
| `google/gemini-3.1-flash-lite-image` | Nano Banana 2 Lite | image, text | image, text | 0.25 | 1.50 | 0.00003 |
| `google/gemini-3-pro-image-preview` | Nano Banana Pro (preview) | image, text | image, text | 2.00 | 12.00 | 0.00012 |
| `google/gemini-2.5-flash-image` | Nano Banana | image, text | image, text | 0.30 | 2.50 | 0.00003 |
| `openrouter/auto`, `openrouter/auto-beta` | Auto routers | text, image, audio, file, video | image, text | route-dependent | route-dependent | route-dependent |

**Cost-unit note (needed for Section 9).** OpenRouter's `pricing` object is per-token for every field. For image-output models the catalog exposes an `image_output` rate instead of a flat per-image price, and the provider bills a generated image as a fixed block of output tokens. Deriving from the published figures: `image_output 0.00012` × 1,120 output-image tokens = **$0.134** per image for Nano Banana Pro, which matches that model's published per-image price; `image_output 0.00006` × 1,290 = **$0.077** for Nano Banana 2; `image_output 0.00003` × 1,290 = **$0.039** for Nano Banana 2 Lite and for Nano Banana 2.1; `image_output 0.000008` × 1,290 = **$0.010** for GPT-5 Image Mini. Section 9 uses these derived per-image figures, and labels them as derived rather than as quoted list prices.

### 1.4 Weather provider verification

Open-Meteo was checked live on 2026-10-25 and needs **no API key**:

- `GET https://geocoding-api.open-meteo.com/v1/search?name=Hartford&count=1` → returns latitude `41.76371`, longitude `-72.68509`, and `timezone: "America/New_York"`.
- `GET https://api.open-meteo.com/v1/forecast?...&hourly=temperature_2m,precipitation_probability,weather_code&temperature_unit=fahrenheit&timezone=auto&start_date=2026-10-28&end_date=2026-10-28` → returns 24 hourly entries for the requested date.
- A date beyond the window returns a structured error, not a silent wrong answer: `{"error":true,"reason":"Parameter 'start_date' is out of allowed range from 2026-07-24 to 2026-11-09"}`. The accepted window is roughly **16 days ahead and 92 days behind**. This exact error shape is the basis of the out-of-range fallback in `weather.py`.

---

## 2. Global decisions

| Concern | Decision | Applies to |
|---|---|---|
| Backend language | Python 3.11 | `app.py`, `db.py`, `weather.py`, `generator.py`, `critique.py`, `eval.py`, tests |
| Front-end language | Vanilla ES2022 JavaScript (native ES modules) + CSS (no build step) | `static/app.js`, `static/js/*.js`, `static/index.html`, `static/style.css`, `static/css/*.css` |
| Deployment | Render web service, Docker, SQLite file on a persistent disk | whole app |
| Secret handling | Server-side environment variables only | whole app |
| Provider access | OpenRouter REST over HTTPS from the server only | `generator.py`, `critique.py` |
| Weather access | Open-Meteo public API from the server only | `weather.py` |

**Why Python for the backend (alternative considered).** Python 3.11 was chosen because the whole data path is I/O-bound HTTP plus a file-backed SQL database: FastAPI gives typed request/response models and OpenAPI docs for the `/api/*` surface, `httpx` gives one async client shared by the OpenRouter and Open-Meteo calls, and `sqlite3` is in the standard library, so the persistence layer needs no server, no driver install, and no separate container on Render. The team already writes Python, and the assignment requires every member to explain every part — a single backend language keeps the comprehension defense tractable.
**Alternative considered: Node.js + TypeScript (Express/Fastify + `better-sqlite3`).** Genuinely competitive: one language across the whole stack, and `better-sqlite3` is synchronous and fast. Rejected because the team has no shared Node/TypeScript toolchain, and because Python's stdlib `sqlite3` plus `pytest` removes an entire class of dependency and async-debugging work that this project does not need. Reconsider if a front-end framework is adopted later (see Section 6).

**Why vanilla JavaScript for the front end (alternative considered).** The front end is one page with four panels (auth dialog, wardrobe tray, brief panel, three-card result showcase, remix editor, saved-looks drawer) and no shared mutable state beyond the current brief and the current result set. A framework would add a bundler, a dev server, and a build step to a project that must run from `python app.py` on a free Render tier and be explainable line by line in ten minutes of presentation time.
**Alternative considered: React + Vite.** Rejected on build/deploy complexity and because React's component model buys nothing for a page with a single document and a handful of imperative panels.
**Alternative considered: Svelte or Alpine.js.** Svelte would be the natural "lightweight framework" pick and was the runner-up; Alpine was rejected outright as too small for the upload tray and remix editor state.
**Module layout (decided 2026-10-26):** the client is split into native ES modules (`static/app.js` as the entry, feature modules under `static/js/`) loaded with `<script type="module">`. Browsers resolve the imports directly, so there is still no build step, bundler, or dev server.
**Consequence, recorded honestly:** because there is no build step, there is no TypeScript type-checking on the client. The critique JSON contract from Section 7 is validated on the **server** in `critique.py` before it reaches the client, and the client treats the payload as untrusted. This is a deliberate trade: one contract, one validator, one place to change it.

**Why SQLite (alternative considered).** The data is small, single-node, and relational: users, sessions, wardrobe items, generated looks, critique records. Rows are user-owned and read by owner only. `sqlite3` is in the Python standard library and needs no daemon. On Render the database file lives on a mounted persistent disk so it survives redeploys.
**Alternative considered: PostgreSQL (hosted).** Better for concurrent writes and horizontal scale, but it adds a hosted-database account, a connection pool, migrations, and a second thing to keep alive — for a three-person course project whose entire dataset is a few megabytes, that is unjustified operational surface. It stays the escape hatch if the app ever needs multiple web-service instances.

---

## 3. Component specifications

---

### 3.1 Component A — App server (`app.py`)

#### What it does

The single HTTP entry point. It owns four responsibilities and nothing else: request routing, authentication and session enforcement, orchestration of the other components, and serving the static front end. It contains **no** SQL statements, **no** HTTP calls to OpenRouter or Open-Meteo, and **no** business rules about outfits. Those belong to `db.py`, `weather.py`, `generator.py`, and `critique.py`. This separation is what makes the unit tests possible: the logic under test lives in modules that can be imported and exercised without a running server or a network.

#### Language

Python 3.11 with FastAPI and Uvicorn.

**Alternative considered: Flask.** Flask is smaller and the team knows it, but Flask has no native typed request/response models, so every endpoint would hand-roll validation and every error response would be hand-shaped. FastAPI generates the OpenAPI schema for free, which gives the front end a machine-readable contract and gives the Playwright test a stable list of routes to assert on. The extra dependency is worth it.

#### Model

**This component makes no model calls of its own.** It calls `generator.py` and `critique.py`, which own their own model decisions (Sections 3.4 and 3.5). The app server's model-related responsibility is only to pass the selected critique model name through to `critique.py` as an opaque string, so the cheap/strong comparison can be switched by request rather than by code change.

#### Interfaces

HTTP API, all under `/api`. All request and response bodies are JSON except the two file uploads, which are `multipart/form-data`.

| Method | Path | Auth | Request | Response (200) |
|---|---|---|---|---|
| GET | `/api/health` | none | — | `{"status":"ok","database":true,"openrouter_key_configured":bool,"weather_key_configured":bool,"version":str}` |
| POST | `/api/auth/register` | none | `{"username":str,"password":str}` | `{"user_id":int,"username":str,"created_at":str}` |
| POST | `/api/auth/login` | none | `{"username":str,"password":str}` | `{"user_id":int,"username":str}` + `Set-Cookie: fitlab_session=<opaque>` (HttpOnly, SameSite=Lax, Secure in production) |
| POST | `/api/auth/logout` | session | — | `{"ok":true}` + session cookie cleared |
| GET | `/api/auth/me` | session | — | `{"user_id":int,"username":str}` |
| GET | `/api/wardrobe` | session | — | `{"items":[<wardrobe item>, ...]}` |
| POST | `/api/wardrobe/upload` | session | multipart: `file` (bytes), `category` (one of `top,bottom,outerwear,shoes,accessory,full_outfit`), `label` (str, optional) | `{"item":<wardrobe item>,"rejected":false}` or `{"item":null,"rejected":true,"reason":str,"code":str}` |
| DELETE | `/api/wardrobe/{item_id}` | session (owner) | — | `{"ok":true}` |
| GET | `/api/weather` | session | query: `event_date` (ISO `YYYY-MM-DD`), `event_time` (24h `HH:MM`), `city` (optional), `lat`/`lon` (optional) | `<weather summary>` (Section 3.3) |
| POST | `/api/outfits/generate` | session | `{"occasion":str,"aesthetic":str,"styling_preference":str,"event_date":str,"event_time":str,"city":str?,"lat":float?,"lon":float?,"selected_item_ids":[int],"notes":str?}` | `{"job_id":str,"status":"queued"}` (202) |
| GET | `/api/outfits/{job_id}` | session (owner) | — | `{"job_id":str,"status":"queued|running|complete|failed","options":[<outfit option>, ...],"weather":<weather summary>,"error":str?}` |
| POST | `/api/outfits/remix` | session | `{"source_job_id":str,"selected_pieces":[<piece>, ...],"instructions":str,"event_date":str,"event_time":str,"city":str?}` | `{"job_id":str,"status":"queued"}` (202) |
| POST | `/api/looks` | session | `{"job_id":str,"option_index":int}` | `{"look":<saved look>}` |
| GET | `/api/looks` | session | query: `occasion` (optional), `from_date`/`to_date` (optional ISO) | `{"looks":[<saved look>, ...]}` |
| DELETE | `/api/looks/{look_id}` | session (owner) | — | `{"ok":true}` |
| GET | `/` and other static paths | none | — | `static/index.html`, `static/app.js`, `static/js/*.js`, `static/style.css`, `static/css/*.css`, `static/fonts/*` |

**Outfit option shape** (returned inside `/api/outfits/{job_id}`):

```
{
  "index": 0,
  "image_data_url": "data:image/png;base64,...",
  "pieces": [ {"id":"p1","name":"navy wool overcoat","category":"outerwear","color":"navy","source":"generated"} ],
  "attempts": 2,
  "critique": <critique JSON, Section 7>,
  "critique_history": [ <critique JSON>, ... ],
  "unresolved": [ <mismatch object>, ... ],
  "generation_model": "google/gemini-3.1-flash-image",
  "critique_model": "xiaomi/mimo-v2.6-flash"
}
```

**Job model.** Generation is asynchronous because a full generate-plus-critique-plus-retry cycle on three options takes tens of seconds; the endpoint contract therefore splits submit from poll. Jobs are held in an in-process table keyed by `job_id` and mirrored into the `jobs` table in SQLite so that a poll after a server restart returns `failed` with an explanatory error rather than hanging.

#### Dependencies

| Dependency | Why |
|---|---|
| `fastapi`, `uvicorn` | HTTP routing, typed bodies, OpenAPI schema |
| `db.py` | All persistence. The app server issues no SQL of its own. |
| `weather.py` | Resolves the event-time forecast; returns "unavailable" rather than blocking |
| `generator.py` | Produces the three outfit images and the piece lists |
| `critique.py` | Scores each generated image and drives the retry decision |
| `python-multipart` | Parsing `multipart/form-data` uploads |
| `httpx` | Shared async HTTP client, also used by `weather.py` and `generator.py` |
| `passlib[bcrypt]` or `argon2-cffi` | Password hashing. Plain SHA-256 is not acceptable; see DB-3. |
| `itsdangerous` or `secrets`-based opaque tokens | Session cookie signing and random session-token generation |

**Deliberately absent:** no Redis, no Celery, no message broker. The job table is in SQLite and the worker is an `asyncio` task inside the same process. A broker would be needed only if generation outlived a single process.

#### Behaviors

- **APP-1** — The server starts with `uvicorn app:app` on port `8000` (or `$PORT`), serving the static front end from `static/` and the API from `/api/*`.
- **APP-2** — `OPENROUTER_API_KEY` is read from the process environment at call time. It is never written to a response body, a log line, a static asset, an error message, or an exception traceback. `GET /api/health` reports only a **boolean** indicating whether the key is configured.
- **APP-3** — Every endpoint except `/api/health`, `/api/auth/register`, `/api/auth/login`, and the static assets requires a valid session cookie. A request without one receives `401` with body `{"detail":"authentication required"}`. This check runs in middleware, so it cannot be forgotten on a new endpoint.
- **APP-4** — `POST /api/outfits/generate` and `POST /api/outfits/remix` return `202` with a `job_id` immediately; the actual work happens in the background. `GET /api/outfits/{job_id}` reports progress.
- **APP-5** — A job belonging to another user's `user_id` returns `404`, not `403`. The app never confirms that a resource id exists but is not yours.
- **APP-6** — Every mutation (`upload`, `generate`, `remix`, `save`, `delete`) is scoped to the authenticated `user_id` at the `db.py` call. No endpoint accepts a `user_id` from the client.
- **APP-7** — A request body that fails validation returns `422` with FastAPI's validation body, and the error text is safe to show the user (it echoes field names, never secrets).
- **APP-8** — Unhandled exceptions in a background job are caught, the job status becomes `failed`, and the stored error message is a human-readable sentence. Stack traces go to the server log only.
- **APP-9** — `GET /api/health` returns `200` only when the database file opens and a trivial query succeeds; it returns `503` with `{"status":"degraded"}` otherwise, so the Render health check can distinguish "process up" from "process usable".
- **APP-10** — The static front end is served with no inline secrets and no server-rendered user data; all user data arrives via `/api/*` JSON.
- **APP-11** — Uploads are capped at 10 MB per file and rejected with `413` above that, before the bytes are written anywhere.
- **APP-12** — Session cookies are `HttpOnly` and `SameSite=Lax`; `Secure` is added when the deployment is behind HTTPS. A session expires after 30 days of inactivity.

#### Failure handling

| Failure | Response | User-visible wording |
|---|---|---|
| Missing/invalid `OPENROUTER_API_KEY` | `503` on generate/remix | "The styling service is not configured right now. Please try again later." |
| OpenRouter returns non-2xx | job status `failed`, `error` field | "The image service did not respond properly. Please try again." |
| OpenRouter returns 429 (rate limit) | job status `failed` | "The image service is busy right now. Please try again in a minute." |
| OpenRouter returns 200 with no image in the payload | that option is marked failed; the other two options still return | "One of the three outfit ideas could not be drawn. The other two are ready." |
| Weather lookup fails | generation continues, `weather.available = false` | "Weather is unavailable for that date, so these outfits were made without weather guidance." |
| Critique model returns invalid JSON | that option carries `critique.status = "failed"` and `retry_recommended` is not set | "We could not check this outfit against your brief. Here is the image without a score." |
| Critique model returns 500/429 | same as invalid JSON | same as above |
| Database locked or disk error | `500`, error body has no SQL text | "We could not save that right now. Please try again." |
| Session cookie invalid or expired | `401` | "Please sign in again." |
| Uploads blocked as containing people | `200` with `rejected: true` | "That photo looks like it shows a person. Please upload clothing only — a flat lay or a piece on a hanger." |

---

### 3.2 Component B — Database (`db.py`)

#### What it does

Owns the schema and every SQL statement in the project. Provides typed helper functions to the other components; it never calls out to the network and never imports `app.py`. All access is parameterized (`?` placeholders) — string-formatted SQL is not permitted anywhere in this file, because two of the tables hold user-controlled text.

#### Language

Python 3.11 with the standard-library `sqlite3` module. No ORM.

**Alternative considered: SQLAlchemy 2.0 ORM with a PostgreSQL backend.** Rejected for the reasons in Section 2: it adds a dependency, a second service to operate, and a migration story, in exchange for features (unit-of-work, lazy relationships, cross-database portability) this app does not use. The schema is seven tables and every query is one to four joins. Plain SQL is more explainable in the comprehension defense, which matters more here than convenience.
**Note for the record:** if the schema grows past ~10 tables or a second service needs to read it, SQLAlchemy + PostgreSQL is the natural migration and `db.py` is the only file that would change, because nothing else writes SQL.

#### Model

**No model calls.** The database stores model outputs, it never produces them. One field is worth calling out: the critique JSON from Section 7 is stored as a single `TEXT` column containing the validated JSON document, plus a small number of promoted scalar columns (`overall_score`, `retry_recommended`) so the saved-looks list can sort and filter without parsing JSON in SQL. The full JSON stays authoritative.

#### Interfaces

Module-level functions. Every function that touches user data takes `user_id` as its first argument after the connection, so ownership filtering cannot be forgotten.

```
init_db(path) -> None
create_user(username: str, password_hash: str) -> int
get_user_by_name(username: str) -> row | None
create_session(user_id: int, token: str, expires_at: str) -> None
get_session_user(token: str) -> int | None
delete_session(token: str) -> None

add_wardrobe_item(user_id, category, label, filename, mime, byte_size, width, height, sha256, upload_path) -> int
list_wardrobe_items(user_id) -> list[row]
delete_wardrobe_item(user_id, item_id) -> bool

create_job(user_id, kind, brief_json, weather_json) -> str
update_job(job_id, status, options_json, error) -> None
get_job(user_id, job_id) -> row | None

save_look(user_id, job_id, option_index, image_path, pieces_json, brief_json, critique_json, weather_json, unresolved_json) -> int
list_looks(user_id, occasion=None, from_date=None, to_date=None) -> list[row]
delete_look(user_id, look_id) -> bool
```

**Schema.**

```
users(
  id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
)

sessions(
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
)

wardrobe_items(
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  category TEXT NOT NULL,
  label TEXT,
  filename TEXT NOT NULL,
  mime TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  width INTEGER, height INTEGER,
  sha256 TEXT NOT NULL,
  upload_path TEXT NOT NULL,
  preflight_json TEXT NOT NULL,
  created_at TEXT NOT NULL
)

jobs(
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  brief_json TEXT NOT NULL,
  weather_json TEXT,
  options_json TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)

looks(
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_id TEXT,
  option_index INTEGER NOT NULL,
  title TEXT,
  occasion TEXT,
  event_date TEXT,
  image_path TEXT NOT NULL,
  pieces_json TEXT NOT NULL,
  brief_json TEXT NOT NULL,
  critique_json TEXT NOT NULL,
  weather_json TEXT,
  unresolved_json TEXT NOT NULL,
  overall_score INTEGER,
  retry_recommended INTEGER,
  created_at TEXT NOT NULL
)

settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)
```

Indexes: `sessions(user_id)`, `sessions(expires_at)`, `wardrobe_items(user_id)`, `jobs(user_id, created_at)`, `looks(user_id, created_at)`, `looks(user_id, occasion)`.

#### Dependencies

| Dependency | Why |
|---|---|
| `sqlite3` (stdlib) | The database engine |
| `hashlib` (stdlib) | SHA-256 of uploaded bytes, for duplicate detection and integrity |
| `secrets` (stdlib) | Random session tokens |
| `pathlib` (stdlib) | Filesystem paths for the stored uploads |

#### Behaviors

- **DB-1** — `init_db` creates the schema if absent and is idempotent; running it against an existing database changes nothing. The app calls it at startup.
- **DB-2** — Every query that reads or writes user-owned data carries `user_id` in the `WHERE` clause. Ownership is enforced in the data layer as well as at the route, so a future endpoint that forgets the route-level check still cannot leak another user's rows.
- **DB-3** — Passwords are stored as a salted hash from a memory-hard KDF (bcrypt or Argon2id) via `passlib`/`argon2-cffi`. Plain SHA-256 and unsalted fast hashes are prohibited: they are trivially brute-forced from a leaked database. Login compares with a constant-time comparison and returns the same generic message for "no such user" and "wrong password".
- **DB-4** — Usernames are unique case-insensitively (`COLLATE NOCASE`); registration of a duplicate returns a clear "that username is taken" message, not a raw `IntegrityError`.
- **DB-5** — Foreign keys are enforced: `PRAGMA foreign_keys = ON` on every connection. Deleting a user cascades to sessions, wardrobe items, jobs, and looks.
- **DB-6** — `PRAGMA journal_mode = WAL` is set so a long read does not block the write that saves a look.
- **DB-7** — Uploaded bytes are hashed with SHA-256 before storage; a duplicate upload by the same user is rejected with a "you already uploaded this item" message rather than stored twice.
- **DB-8** — The critique JSON stored on a look is byte-identical to the JSON the critique module validated, so the saved look and the live result cannot drift.
- **DB-9** — Saved looks store the weather context **as it was at generation time**, including `available: false` if the forecast was unavailable. A saved look never re-fetches the forecast on read, so the label "generated without weather guidance" stays truthful.
- **DB-10** — `list_looks` filters by `user_id` first, then by optional occasion and date range; the date range applies to the event date stored on the look, not to the save timestamp.
- **DB-11** — The database file lives at a path from the `FITLAB_DB_PATH` environment variable, defaulting to `./fitlab.db`. On Render this points at the mounted persistent disk.
- **DB-12** — Every write happens inside a transaction; a failed transaction leaves the database unchanged.

#### Failure handling

| Failure | Handling |
|---|---|
| Database file missing at startup | `init_db` creates it; if the directory is not writable, the process exits with a clear message naming the path |
| `sqlite3.OperationalError: database is locked` | Retry the write up to 3 times with a 200 ms backoff, then return a 500 with "we could not save that right now" |
| `IntegrityError` on duplicate username | Mapped to a 409 with "that username is taken" |
| Disk full while storing an upload | The upload is rejected before the row is written; the orphaned file is deleted |
| Corrupt database file | Startup fails loudly with the path and the sqlite error text; the app does not silently recreate and lose data |

---

### 3.3 Component C — Weather (`weather.py`)

#### What it does

Resolves one question: *what will the weather be like at the event date, time, and place?* Given an event date, an event time, and either a city name or a browser-provided coordinate, it returns a structured weather summary, **or** an explicit statement that weather is unavailable. It never invents conditions, and it never blocks the rest of the app.

#### Language

Python 3.11 with `httpx` (async) or `urllib.request` (stdlib, sync).

**Alternative considered: Node.js `fetch`.** Rejected because the weather module has to run inside the same Python process as the app server and be importable by `tests/test_weather.py` without a server. A second language for one module buys nothing.
**Alternative considered: a paid commercial API (OpenWeather, WeatherAPI).** Rejected for two reasons. First, cost and key management: Open-Meteo is free and keyless, which removes a second secret and a second failure surface. Second, forecast window: Open-Meteo covers roughly 16 days ahead, and a forecast the user plans around weeks out is usually the best available anyway. If a future version needed longer-range outlooks, the interface would not change — only the provider behind it.

#### Model

**No model calls.** Weather is retrieved from Open-Meteo, not generated. This is deliberate: a language model asked "what will the weather be in Hartford on November 2?" would produce a confident-sounding hallucination, and the intent document for weather explicitly forbids presenting invented conditions as a forecast. The weather service therefore has a **hard no-model rule**.

One place a model *is* used downstream: the weather summary is passed into the generation prompt and the critique rubric, so the wording of the summary is part of what the vision model reads. That is text conditioning, not a weather forecast.

#### Interfaces

```
resolve_weather(
    event_date: str,        # ISO YYYY-MM-DD
    event_time: str,        # 24-hour HH:MM
    city: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    client: httpx.Client | None = None   # injected in tests
) -> WeatherSummary
```

`WeatherSummary` is a plain dataclass:

```
{
  "available": True,
  "location_name": "Hartford, Connecticut, United States",
  "latitude": 41.76371,
  "longitude": -72.68509,
  "timezone": "America/New_York",
  "event_local_datetime": "2026-10-28T18:00",
  "temperature_f": 52.6,
  "feels_like_f": 51.0,
  "precipitation_probability": 20,
  "precipitation_mm": 0.0,
  "wind_speed_mph": 6.8,
  "weather_code": 3,
  "condition_label": "Overcast",
  "layering_advice": "light layering; a mid-weight jacket",
  "unavailable_reason": None
}
```

When the forecast is unavailable the same dataclass is returned with `available = False`, `temperature_f = None`, every metric `None`, and `unavailable_reason` set to one of a fixed set of reason codes. The shape is identical so callers never need a null check on the object itself, only on the fields.

| Reason code | Meaning |
|---|---|
| `OUT_OF_FORECAST_RANGE` | Event date is outside the provider's window; provider returned the out-of-range error |
| `PROVIDER_ERROR` | Provider returned a non-2xx response or a malformed body |
| `NETWORK_ERROR` | The request timed out or the connection failed |
| `LOCATION_NOT_FOUND` | City geocoding returned no result |
| `INVALID_EVENT_TIME` | The event time does not fall on an hourly slot the provider returned |

`condition_label` maps WMO weather codes to a short label (`"Clear"`, `"Partly cloudy"`, `"Overcast"`, `"Fog"`, `"Drizzle"`, `"Rain"`, `"Snow"`, `"Thunderstorm"`, `"Freezing rain"`).

#### Dependencies

| Dependency | Why |
|---|---|
| `httpx` | Async HTTP with timeouts; the same client library used by `generator.py` and `critique.py` |
| `zoneinfo` (stdlib) | Converting the event's local date/time to UTC for the provider's hourly index, and formatting the display string in the event's own timezone |
| `datetime` (stdlib) | Date arithmetic and the 16-day window check |

**No API key.** `WEATHER_API_KEY` in `plan.md` is optional and, if set, is used only to raise the provider's rate limit; it is never required and never sent anywhere but to the weather provider.

#### Behaviors

- **WX-1** — The event date and time are interpreted in the **event location's timezone**, not the browser's timezone and not UTC. The location's IANA zone comes from the geocoding response.
- **WX-2** — Location precedence is: explicit `city` argument > explicit `lat`/`lon` > the browser-detected coordinates passed down from the client. A user-entered city always wins over the detected location, so overriding works even when the browser later reports a different position.
- **WX-3** — A city name is resolved with Open-Meteo geocoding; the first result is used, and the resolved `location_name` is returned so the client can display "Hartford, Connecticut, United States" rather than the raw input.
- **WX-4** — Hourly values are read for the hour containing the event time, and the returned `event_local_datetime` reflects the local wall-clock time of the event.
- **WX-5** — If the event date is outside the provider's accepted range, the provider's structured error is detected and the function returns `available = False, unavailable_reason = "OUT_OF_FORECAST_RANGE"`. The provider's own error text is **not** shown raw to the user; it is logged server-side and summarized as "that date is too far ahead for a forecast".
- **WX-6** — Network failures, timeouts, and non-2xx responses all return `available = False` with `PROVIDER_ERROR` or `NETWORK_ERROR`. The weather lookup never raises out of `resolve_weather`; the generator must never have to handle a weather exception.
- **WX-7** — A city that geocodes to nothing returns `available = False, unavailable_reason = "LOCATION_NOT_FOUND"`, and generation continues.
- **WX-8** — The returned summary includes `layering_advice`, a short human-readable instruction derived deterministically from the numeric values (temperature bands, precipitation probability, wind). This is a rules table in `weather.py`, not model output.
- **WX-9** — `resolve_weather` accepts an injected HTTP client, so `tests/test_weather.py` exercises every branch — success, city override, out-of-range, provider error, network error — with **no API key and no network access**.
- **WX-10** — The function is pure with respect to global state: two calls with the same inputs return the same summary.
- **WX-11** — A cached forecast is reused for identical `(lat, lon, event_date, event_time)` requests within a process for 10 minutes, so polling a running job does not re-hit the provider three times.

#### Failure handling

| Failure | Handling | Effect on the rest of the app |
|---|---|---|
| Out of forecast range | `available = False`, `OUT_OF_FORECAST_RANGE` | Generation proceeds without weather; the result is labeled "generated without weather guidance" |
| Provider 5xx | `available = False`, `PROVIDER_ERROR` | Same |
| Timeout / DNS failure | `available = False`, `NETWORK_ERROR` | Same |
| City not found | `available = False`, `LOCATION_NOT_FOUND` | Same; the client shows the resolved-location field as empty and asks the user to retype the city |
| Provider returns a day but not the requested hour | `available = False`, `INVALID_EVENT_TIME` | Same |

**In every failure row above, generation continues.** This is a hard requirement from `intent/event-weather.md`: "Unavailable forecasts and failed weather lookups do not block outfit generation."

---

### 3.4 Component D — Generator (`generator.py`)

#### What it does

Turns a styling brief into images. It builds a prompt from the occasion, requested aesthetic, styling preference, event-time weather summary, and any selected wardrobe pieces; calls an image model on OpenRouter; and returns three distinct outfit images plus a machine-readable list of the clothing pieces visible in each. It also handles the regeneration pass that the critique loop requests.

#### Language

Python 3.11 with `httpx`.

**Alternative considered: calling the image model from the browser.** Rejected outright — it would require the `OPENROUTER_API_KEY` in client-side JavaScript, which the assignment forbids ("API keys stay in the environment") and which `tests/test_browser.py` asserts against. This is the single most important architectural boundary in the project.

#### Model

**Chosen: `google/gemini-3.1-flash-image` (Nano Banana 2).**

Rationale, in order of weight:

1. **It accepts image input and produces image output.** Its `architecture` is `text+image->text+image` with `input_modalities: [image, text]`. This is the hard requirement: `intent/clothing-uploads.md` demands that selected uploaded pieces "preserve ... their visible colors, patterns, shape, and distinguishing details", and the only way to attempt that is image-conditioned generation. Text-only image models cannot see a reference photo.
2. **Cost.** $0.50/Mtok prompt and $3.00/Mtok completion, with a derived per-image cost of about **$0.077** (Section 1.3). Three options × up to three attempts × three retries is nine images per request; at ~$0.077 that is under $0.70 of image cost per request.
3. **Context.** 131,072 tokens, which comfortably holds several base64 reference images alongside the prompt.

**Alternative considered: `google/gemini-3-pro-image` (Nano Banana Pro).** Better prompt adherence and reference fidelity — the property that matters most for the upload-fidelity requirement. Rejected as the *default* because it costs roughly 4× more per image (derived ≈$0.134/image at the 1,120-token billing block, and $2.00/Mtok prompt versus $0.50/Mtok), and because the fidelity score is checked and disclosed by the critique rather than guaranteed. **Retained as the alternative to benchmark against in `eval.py`**, and selectable per request through a server-side environment variable (`FITLAB_IMAGE_MODEL`) so the comparison is a configuration change, not a code change.
**Second alternative: `google/gemini-3.1-flash-lite-image` (Nano Banana 2 Lite).** Cheapest live option at a derived ≈$0.039/image. Rejected as the default because garment detail is exactly where a Lite tier loses fidelity, and fidelity is a stated success criterion. Worth evaluating if per-request cost becomes a problem.
**Third alternative: `openai/gpt-5-image-mini`.** Also image-conditioned and cheap (derived ≈$0.010/image), but it has the smallest commercial dependency of the three and no published per-image figure on OpenRouter beyond the rate field.

**Slugs that were considered and are gone:** `black-forest-labs/flux-1-schnell` and `recraft/recraft-v3`, both named in `plan.md`. Neither appears anywhere in the current catalog, and no OpenRouter model ID contains "flux" or "recraft" at all. They are not merely deprecated — they are unreachable, and the `plan.md` row for `generator.py` must be corrected. Note also that neither would have satisfied requirement (1) anyway: both are text-to-image only, so the upload-fidelity feature in `plan.md` was never implementable with them.

#### Interfaces

```
build_prompt(brief: Brief, weather: WeatherSummary, references: list[RefImage]) -> str
generate_image(prompt: str, references: list[RefImage], seed: int | None = None) -> GeneratedImage
generate_options(brief, weather, refs, count: int = 3) -> list[GeneratedImage]
extract_pieces(prompt, image) -> list[Piece]      # one extra text-model call, see below
```

```
Brief = {
  "occasion": str,             # e.g. "senior-year dinner"
  "aesthetic": str,            # e.g. "relaxed, clean, smart"
  "styling_preference": str,   # e.g. "masculine" — a per-request choice, not an app setting
  "event_date": str, "event_time": str,
  "location_name": str | None,
  "notes": str | None,
  "preserve_pieces": [ {"piece_name": str, "source_item_id": int | None} ],
  "revision_instructions": str | None
}

GeneratedImage = {
  "image_data_url": str,       # data:image/png;base64,...
  "seed": int | None,
  "model": str,
  "prompt": str,               # the exact prompt sent, stored for reproducibility
  "raw_bytes": bytes,
  "mime": str
}

Piece = {
  "id": str, "name": str, "category": str,
  "color": str | None, "pattern": str | None,
  "source": "generated" | "upload" | "preserved"
}
```

**Piece identification.** Image models do not return a structured garment list. The generator therefore makes **one additional cheap text-vision call** after the image is produced, using `xiaomi/mimo-v2.6-flash` (the same cheap model used for critique, at $0.14/Mtok) with the generated image attached, asking for a JSON array of visible garments. This is a reuse of an existing dependency rather than a new model decision, and it costs a fraction of a cent per outfit. `intent/outfit-generation.md` requires that "Each option displays a generated image and identifies its individual clothing pieces", so this step is necessary, not optional.

#### The generation prompt

The prompt is assembled from fixed sections in a fixed order, so that a diff of two prompts shows exactly what changed between a first attempt and a retry:

1. **Subject line** — "Full-body fashion look on a neutral, faceless, featureless display mannequin. The mannequin is a fictional object, not a person: no face, no skin, no hands, no identifiable features."
2. **Wardrobe line** — if references are present: "Recreate the following uploaded garment(s) as faithfully as possible, preserving visible color, pattern, cut, and distinguishing details: <list>." Each reference image is attached alongside the prompt.
3. **Occasion line** — the brief's occasion, phrased as a dress requirement ("evening sit-down dinner — smart, not business formal").
4. **Aesthetic line** — the requested aesthetic, quoted verbatim.
5. **Styling-preference line** — the brief's styling preference.
6. **Weather line** — only when `weather.available` is true: "Outdoor conditions at the event: 52°F, overcast, 20% chance of precipitation. Practical guidance: <layering_advice>." When weather is unavailable this line is **omitted entirely** — it is never replaced with "assume mild weather".
7. **Diversity line** — for option *k* of *n*: "Option {k+1} of {n}. This must be a complete, coherent outfit at the same formality level as the others, not a more casual or more formal variant, and must not repeat the same garments or the same silhouette as the other options."
8. **Preservation line** — for retries only: the specific feedback being acted on, quoted from the critique's mismatch explanations.
9. **Revision line** — for remixes only: the user's written revision instructions, verbatim, plus the list of pieces that must be preserved.
10. **Provenance line** — "Generated image. Fictional mannequin; no real person is depicted."

#### Dependencies

| Dependency | Why |
|---|---|
| `httpx` | The OpenRouter chat-completions call, with the image payload |
| `base64` (stdlib) | Encoding the reference images and the response image as data URIs |
| `critique.py` | Only for the piece-identification call, which reuses the cheap model configured there. `generator.py` does not import the critique logic. |
| `weather.py` | Only the dataclass type; the generator reads fields, it never calls the provider |

The generator calls OpenRouter directly with the `Authorization: Bearer $OPENROUTER_API_KEY` header, server-side only. It sends **no** user identity, username, or free-text note other than the brief itself; the note field is limited to 400 characters to keep the payload bounded.

#### Behaviors

- **GEN-1** — A brief produces exactly **three** options. If one generation call fails, the other two are still returned, and the failed slot is reported with an error rather than silently omitted.
- **GEN-2** — The three options are equally suitable for the brief: the same formality level, differing in silhouette, color family, and garment mix. The diversity line in the prompt is what enforces this; the critique checks it, but the prompt is the primary mechanism.
- **GEN-3** — Every generated image depicts a fictional mannequin with no face, skin, hands, or identifiable features. The prompt states this explicitly on every call.
- **GEN-4** — When reference images are present, each is attached to the request as an `image_url` part with a `data:image/...;base64,...` payload, in the same message as the text prompt. The model receives the actual pixels, not a text description of them.
- **GEN-5** — The exact prompt and the model slug used are recorded on the generated option, so any result can be reproduced or explained later.
- **GEN-6** — Each option's image is stored under a content-addressed path derived from the job id and option index, and the option carries a `data_url` for immediate display plus a server path for later saving.
- **GEN-7** — The generator performs **no** retry of its own on a failed HTTP call. Retry is the critique controller's responsibility and is bounded there (CRT-12). Two independent retry loops would multiply the cost ceiling.
- **GEN-8** — `generate_options` issues the three image calls **concurrently** rather than sequentially, because each takes several seconds and the user is waiting.
- **GEN-9** — Reference images are downscaled to a maximum edge of 1024 px and re-encoded as PNG before being sent, so a 10 MB phone photo does not become a 10 MB request body.
- **GEN-10** — The seed is recorded when the provider returns one. A retry uses a **different** seed, so a regenerated image is a genuinely new attempt rather than the same picture with new noise.
- **GEN-11** — The generator never invents or infers a piece that is not visible in the image. The piece list comes from the piece-identification vision call, and the critique is what decides whether that list is accurate.
- **GEN-12** — When `weather.available` is false, the generated prompt contains no weather content whatsoever — the word "weather" does not appear in the prompt string. This is testable directly against the built prompt.

#### Failure handling

| Failure | Handling |
|---|---|
| HTTP 429 from OpenRouter | The option fails with a "busy" message. Other options continue. No automatic retry (GEN-7). |
| HTTP 401 / 403 | The whole job fails with "the styling service is not configured right now" — this is a server misconfiguration, not a user error |
| HTTP 5xx or timeout | That option fails; the other two continue. The user sees which slot is missing. |
| 200 response containing no image payload | That option fails with "the image service returned no picture" |
| Reference image too large or undecodable | The upload is rejected at upload time, so this cannot occur here; if it somehow does, the option is generated without that reference and the omission is disclosed in the option's `notes` |
| Piece-identification call fails | The option is still returned, with an empty `pieces` list and a note that pieces could not be identified. The image itself is not withheld. |

---

### 3.5 Component E — Critique (`critique.py`)

This is the component the assignment is graded on, so it is specified in the most detail. The full JSON contract is Section 7.

#### What it does

Takes a **generated image** — the actual pixels — plus the brief it was meant to satisfy, and any reference images the user selected, and produces a structured assessment: scores against a fixed rubric, plain-language matches and mismatches, explicit statements of what could not be determined from the image, and a machine-readable recommendation on whether the look should be regenerated. It also owns the retry controller.

#### Language

Python 3.11 with `httpx`.

**Alternative considered: Node.js.** Rejected for the same reason as `weather.py`: the critique module must be importable by `tests/test_critique.py` with no server running, and the project has one backend language.

#### Model

**Cheap model: `xiaomi/mimo-v2.6-flash`.**
**Strong model: `minimax/minimax-m3`.**

Both were verified on 2026-10-25 to accept image input (`input_modalities` includes `image` for both) and to emit text only, which is exactly what a structured critique needs. Both were tested on receipts in the Week 5 lab, which is the same "read an image, judge it against a written spec, emit structured output" task this component performs — the receipt lab is the prior art for this pipeline.

| | `xiaomi/mimo-v2.6-flash` | `minimax/minimax-m3` |
|---|---|---|
| Input modalities | text, image, video, audio | text, image, video |
| Context window | 1,050,000 | 1,048,576 |
| Prompt price | $0.14 / Mtok | $0.30 / Mtok |
| Completion price | $0.28 / Mtok | $1.20 / Mtok |
| `reasoning` toggle | supported, `mandatory: false` | supported, `mandatory: false` |
| `response_format` / `structured_outputs` | supported | supported |

**Why these two.** The cheap model is roughly **2.1× cheaper on input and 4.3× cheaper on output** than the strong model, which matters because the critique runs once per generated image and the retry loop can multiply that by three. Both support `response_format`/`structured_outputs`, so the Section 7 contract can be enforced by the provider as well as by our parser — the parser still validates, because a provider-side guarantee is not one we should bet a graded artifact on.

**The reasoning toggle — the important detail.** The OpenRouter catalog reports `reasoning: {"mandatory": false}` for `xiaomi/mimo-v2.6-flash`, but MiMo models emit a reasoning trace by default. If reasoning is left on, the response body contains reasoning text ahead of the JSON document, and the naive `json.loads` on the content string fails. This was observed in the Week 5 lab: **MiMo requires reasoning to be turned off** for structured output to parse. Every MiMo call in `critique.py` therefore sends `reasoning: {"enabled": false}` explicitly, and `tests/test_critique.py` asserts the request body contains that flag. (For contrast, `minimax/minimax-m3.1-flash` was rejected as a candidate precisely because its catalog entry says `reasoning.mandatory = true` — it cannot be turned off at all.)

**Alternatives considered for the cheap slot.**
- `openai/gpt-4o-mini` — named in `plan.md`. Exists, accepts images, $0.15/Mtok prompt and $0.60/Mtok completion. **Rejected as the cheap model** because it is *more expensive than MiMo on both axes* ($0.15 vs $0.14 prompt, $0.60 vs $0.28 completion) while offering a smaller context window (128K vs 1.05M). It stays in `eval.py` as a third comparison point, since `plan.md` committed to it and the eval should show why it was dropped.
- `minimax/minimax-01` — named in `plan.md`. Exists, accepts images, $0.20/Mtok prompt and $1.10/Mtok completion. **Rejected** because `minimax/minimax-m3` is the current version of the same family at comparable cost ($0.30/$1.20) with a newer generation, a larger context window, and video input.

**Alternatives considered for the strong slot.**
- `anthropic/claude-sonnet-5.5` — accepts images, $2.00/Mtok prompt and $10.00/Mtok completion. Roughly **6.7×** the input cost and **8.3×** the output cost of `minimax/minimax-m3`. Rejected as the default strong model on cost, given that the whole project budget guidance is $20 and the critique loop is the highest-volume call in the app. It is a legitimate escalation path: if `minimax/minimax-m3` proves weak on the upload-fidelity check in `eval.py`, the strong slot moves to Claude Sonnet 5.5 for that check only.
- `minimax/minimax-m3.1-flash` — rejected: reasoning is mandatory and cannot be disabled.

**The cheap-vs-strong comparison is a required deliverable** ("a cheap model compared against a stronger one on a real task from the project"). `eval.py` runs the same set of generated outfits through both critique models, on the same briefs, and records in `CHECKS.md`: per-model overall-score agreement with the strong model's own scores, mismatch-detection agreement, retry-trigger agreement, latency, and cost. The real task is *this* project's critique; the comparison is not a generic benchmark.

#### Interfaces

```
critique_image(
    image_bytes: bytes,
    brief: Brief,
    weather: WeatherSummary,
    references: list[bytes],
    model: str = "xiaomi/mimo-v2.6-flash"
) -> CritiqueResult

CritiqueResult = {
  "status": "ok" | "failed",
  "payload": <the Section 7 JSON document>,
  "error": str | None,
  "model": str,
  "latency_ms": int,
  "usage": {"prompt_tokens": int, "completion_tokens": int, "cost_usd": float}
}

run_option_with_retry(brief, weather, references, generator, critique, max_retries: int = 2) -> OptionResult

OptionResult = {
  "image_data_url": str,
  "pieces": [Piece],
  "attempts": int,                 # 1 = initial, 3 = initial + 2 retries
  "critique": CritiqueResult,
  "critique_history": [CritiqueResult],
  "unresolved": [Mismatch],
  "retry_exhausted": bool
}
```

#### The critique prompt

The system prompt is fixed. It tells the model four things, in this order:

1. **What to read.** "You are examining the pixels of a generated fashion image. Describe only what is visibly present: garment types, silhouettes, colors, patterns, layering, materials as they appear, and accessories. Do not infer what you cannot see."
2. **What to compare against.** The brief's occasion, aesthetic, and styling preference, quoted verbatim, plus the weather summary when available.
3. **What to do when the image cannot settle a question.** "If a property such as fabric warmth, waterproofing, exact brand, or fabric weight cannot be established from the image, state it in `uncertainty` and do not score it."
4. **What to output.** The Section 7 schema, with the score scale, the weighting rule, the severity definitions, and the explicit rule that a missing weather forecast means the weather score is `null` and is excluded from the weighted total.

The user message carries the image(s) as `image_url` parts with base64 data URIs, followed by the brief. When reference images exist, they are attached **before** the generated image and labeled, so the model compares a reference against the result rather than describing an unrelated image.

#### Dependencies

| Dependency | Why |
|---|---|
| `httpx` | The OpenRouter chat-completions call |
| `base64` (stdlib) | Encoding the generated image and the reference images as data URIs |
| `json` (stdlib) | Parsing and validating the model's response |
| `re` (stdlib) | Stripping a reasoning trace or a fenced code block if one appears despite the flag |
| `generator.py` | Only the `Brief` type and the image bytes; the critique module does not call the image model |

The critique module has **no dependency on `app.py` and no dependency on `db.py`**, so `tests/test_critique.py` can drive the entire retry logic with a fake generator and a fake critic.

#### Behaviors

- **CRT-1** — The critique receives the **generated image bytes** as a base64 data URI in `messages[].content`, in the same message as the text prompt. It never receives only the prompt. This is the assignment's central requirement and is asserted in `tests/test_critique.py` by inspecting the constructed request payload.
- **CRT-2** — When reference images exist, both the reference images and the generated image are sent. The generated image is the last image part.
- **CRT-3** — The response is parsed with `json.loads`. If it fails, the parser attempts exactly two repairs in order: (a) strip a leading reasoning trace and any fenced code-block wrapper; (b) extract the outermost `{...}` substring. If neither yields valid JSON, the result is `status = "failed"`.
- **CRT-4** — The parsed document is validated against the Section 7 schema. Every required field must be present with the right type. A score outside 0–100, a missing field, a wrong type, or an unknown severity value makes the critique **fail**; it is never silently coerced. A failed critique is not a passing critique.
- **CRT-5** — The overall score is **computed by the server, not read from the model.** The model returns the five dimension scores; `critique.py` applies the weighting rule from Section 7 and rounds. A model that returns its own `overall` that disagrees with the weighted computation by more than 1 is a validation failure.
- **CRT-6** — The weather dimension is scored **only when `weather.available` is true**. Otherwise `scores.weather` is `null`, `weather_assessed` is `false`, and the weight is excluded from the denominator. The model is instructed to return `null` there, and the server enforces it regardless of what the model returns.
- **CRT-7** — The upload-fidelity dimension is scored **only when at least one reference image was supplied**. Otherwise `scores.upload_fidelity` is `null` and `upload_fidelity_assessed` is `false`.
- **CRT-8** — Missing weather alone **never** triggers a retry. The retry decision in CRT-11 is computed from the overall score and the mismatch severities only; `weather_assessed = false` is not a retry trigger. This is an explicit success criterion in `intent/visual-critique.md`.
- **CRT-9** — Properties that an image cannot establish are reported in `uncertainty` and are not scored. The prompt names fabric warmth, waterproofing, exact fabric weight, brand, and fit-on-a-real-body as examples.
- **CRT-10** — Each of the three options is critiqued **independently**. A failing option is regenerated and re-critiqued; the other two are not touched. A successful alternative is never regenerated because another option failed.
- **CRT-11** — **Retry trigger.** A retry is triggered when **either** condition holds: `overall < 70` (strictly less than), **or** any mismatch has `severity` of `"major"` or `"critical"`. A `minor` mismatch alone does not trigger a retry. A `null` weather score alone does not trigger a retry. The exact boolean is carried in the JSON as `retry_recommended`, and the controller uses that field, so the model-visible rule and the controller's rule are the same rule stated once.
- **CRT-12** — **Retry ceiling.** At most **2** automatic retries per look after the initial generation, i.e. at most **3** generation attempts and at most **3** critique calls in total for one look. When the third critique still triggers a retry, the controller **stops**, sets `retry_exhausted = true`, and moves the still-open mismatches into `unresolved`.
- **CRT-13** — After the retry ceiling, the look is still returned. The user sees the image, the scores, and an explicit disclosure of what remains unresolved. The app never presents an unresolved look as a successful match.
- **CRT-14** — Each attempt is critiqued separately and every critique is kept in `critique_history` with its attempt number. The user can see that a look was regenerated and why.
- **CRT-15** — The retry prompt includes the **verbatim** mismatch explanations from the triggering critique, so the next attempt acts on specific feedback rather than a generic instruction.
- **CRT-16** — Each retry uses a different seed (GEN-10) so the regenerated image differs.
- **CRT-17** — If the critique model call itself fails (network, 429, 500, invalid JSON), that attempt is **not** retried by the retry controller, because the retry controller exists to fix image-brief mismatches, not to paper over a transport failure. The option is returned with `critique.status = "failed"` and a clear "we could not check this outfit" message. This prevents a failed critique from burning image-generation budget.
- **CRT-18** — Every critique call records token usage and computed cost, and the per-attempt cost is logged and returned in `CritiqueResult.usage`.
- **CRT-19** — The critique model name used is recorded on the result and on the outfit option, so the eval can attribute scores to a model and the user can see which model judged the look.
- **CRT-20** — The model is instructed to describe only what is visible. The critique never asserts that a look is "comfortable", "warm", or "waterproof" — those go in `uncertainty` unless the image genuinely shows them.

#### Failure handling

| Failure | Handling | User-visible wording |
|---|---|---|
| Model returns invalid JSON after two repairs | `status = "failed"`, no score shown, no retry | "We could not check this outfit against your brief. Here is the image on its own." |
| Model returns valid JSON that violates the schema | `status = "failed"` — same as above. The offending payload is logged server-side but never shown to the user. | Same as above |
| Model returns scores but omits `overall` | **Not a failure.** The server computes `overall` from the dimension scores per Section 7. | normal display |
| Model returns an `overall` that disagrees with the computed value by more than 1 | Validation failure (`status = "failed"`) | same as invalid JSON |
| HTTP 429 from the critique model | `status = "failed"`, `error = "rate_limited"`, no retry | "The review service is busy. Please try again in a minute." |
| HTTP 5xx or timeout | `status = "failed"`, `error = "provider_error"`, no retry | "We could not reach the review service. Please try again." |
| Generated image bytes are unreadable | The option fails before any critique call | "That image could not be read." |
| Reference image unreadable | The reference is dropped and the omission is recorded in `uncertainty`; the critique still runs on the generated image | "We could not compare against one of your reference photos." |

---

### 3.6 Component F — Front end (`static/index.html`, `static/app.js`, `static/js/*.js`, `static/style.css`, `static/css/*.css`, `static/fonts/`)

#### What it does

The single-page client. It renders six regions — the auth dialog, the wardrobe tray, the brief panel, the three-option showcase, the remix editor, and the saved-looks drawer — and it talks **only** to `/api/*`. It holds no API key, no provider name, and no provider URL. It performs no scoring, no retry logic, and no weather interpretation: the server sends fully-formed results and the client renders them.

#### Language

Vanilla ES2022 JavaScript, semantic HTML, and plain CSS with custom properties. No build step, no framework, no bundler. The decision and its alternatives are in Section 2.

**Alternative considered, and rejected again here: Svelte.** It remains the runner-up. Svelte's component model would map well onto the six panels, and its output is small. Rejected because it requires a build step to produce the files that Render serves, and because the project must be runnable with `python app.py` for the demonstration without a second terminal open.

#### Model

**No model calls from the client. This is a hard boundary, not a preference.**

The client contains no occurrence of `OPENROUTER_API_KEY`, `openrouter.ai`, `api_key`, `Bearer`, or any provider slug. `tests/test_browser.py` asserts this in three ways: it scans the delivered `app.js` and `index.html` source for those strings; it records every network request the browser makes during a full generate flow and asserts every request URL starts with the app's own origin and every `/api/*` request carries no `Authorization` header; and it asserts no request reaches `openrouter.ai` or any external host.

**Why the model decision lives server-side.** A key in a browser is a key in every visitor's browser, in the page source, in the browser history, and in any network capture. The assignment treats a committed key as compromised; a key served to the browser is compromised the moment it is written. There is no acceptable version of this feature that runs from the client.

#### Interfaces

The client consumes the API from Section 3.1 and consumes the critique JSON from Section 7. It contributes three things the server cannot get on its own:

| Client capability | How the server gets it |
|---|---|
| **Browser geolocation** | `navigator.geolocation.getCurrentPosition()` → latitude and longitude sent with the brief. The browser prompt is shown by the client; the server never asks for location. |
| **Image preview** | `URL.createObjectURL(file)` for a local preview before upload completes; `revokeObjectURL` after. |
| **Selected pieces** | Piece selections from the showcase are sent as piece objects in the remix request. |

The client sends the browser-detected coordinates **only if the user grants permission**. If permission is denied or is never answered, the client sends `lat: null, lon: null` and the brief panel shows the city field as the location source, which is the documented fallback.

#### Dependencies

| Dependency | Why |
|---|---|
| Browser `fetch` | The only network API used, always same-origin |
| Browser `FormData` | `multipart/form-data` uploads |
| Browser `URL.createObjectURL` | Local image previews without a round trip |
| Browser `navigator.geolocation` | The optional detected-location source |
| No runtime JS library | A CDN script tag would be a third-party request the browser test would flag and a supply-chain surface; there is no dependency that earns one |

#### Behaviors

- **FE-1** — The page loads with the brief panel visible and every other panel hidden. No API call fires before the user acts.
- **FE-2** — On load, the client calls `GET /api/auth/me`. If it returns 200, the app shows the signed-in state and loads the wardrobe and saved looks. If it returns 401, the auth dialog opens. **The client never assumes signed-in state.**
- **FE-3** — The auth dialog is the only way into the styling features. The client hides the panels, but the **server** is what enforces it (APP-3); the client-side hiding is presentation only.
- **FE-4** — Register and login failures are shown in plain language next to the form ("That username and password do not match", "That username is already taken"). The client never renders a stack trace or an HTTP status code to the user.
- **FE-5** — The brief panel collects occasion (required), aesthetic (required), styling preference (a per-request choice: masculine, feminine, unisex), event date (required, no past dates), event time (required), and an optional city override.
- **FE-6** — The brief panel offers an explicit "use my current location" action that triggers the browser geolocation prompt. It never triggers on page load without a click, because an unprompted permission request is hostile and some browsers block it.
- **FE-7** — The location field always displays **which** location was used ("Using Hartford, Connecticut, United States" or "Using your current location"), because the weather intent requires the user to be able to check it.
- **FE-8** — The wardrobe tray accepts drag-and-drop and a file picker, previews each image immediately, and shows the category selector (`top`, `bottom`, `outerwear`, `shoes`, `accessory`, `full_outfit`) per item.
- **FE-9** — Before an upload is sent, the tray states the clothing-only rule in plain words: "Upload clothing only — a flat lay or an item on a hanger. Photos of people are not allowed."
- **FE-10** — A rejected upload shows the server's reason verbatim in the user's terms, including the people-detection rejection.
- **FE-11** — Selecting wardrobe pieces marks them in the tray, and the selection is echoed in the brief panel before generation ("3 pieces selected as the starting point") so the user can see what the request contains.
- **FE-12** — Generation is submitted with a `POST /api/outfits/generate` that returns a `job_id`, and the client **polls** `GET /api/outfits/{job_id}` every 2 seconds until the status is `complete` or `failed`. Polling stops on either terminal state, on a `404` or `401`, or after 5 consecutive transient failures (network error, 5xx, 429, 408). If the page is hidden for more than 60 seconds, polling **pauses** and **resumes** as soon as the page is visible again, so a long job's result is not lost because the user switched tabs. *(Amended 2026-10-26: originally "stops if the page is hidden for more than 60 seconds".)*
- **FE-13** — The three-option showcase renders each option as a card: the image, the identified pieces, the overall score, the per-dimension score badges, the plain-language summary, the mismatch list, and the uncertainty list.
- **FE-14** — A dimension that was not assessed (weather, or upload fidelity with no references) renders as a **"Not assessed"** badge. It is never rendered as a zero and never rendered as a percentage.
- **FE-15** — A look that exhausted its retries renders an explicit unresolved-issues banner listing what did not match. The client never shows such a look as a clean pass.
- **FE-16** — The remix editor lets the user select pieces from more than one option. The current combination is displayed as a visible list of chosen pieces **before** the generate button is enabled, so the combination is never a guess.
- **FE-17** — The remix request sends the user's written instructions verbatim in the `instructions` field.
- **FE-18** — A remixed look is rendered in the same card layout as the original options and receives its own critique, displayed the same way.
- **FE-19** — The saved-looks drawer lists saved looks with their image, occasion, event date, and the weather context they were generated under. When weather was unavailable at generation time, the entry says so and does not re-fetch.
- **FE-20** — Saved looks can be filtered by occasion and by date range, and the filter state is sent to the server as query parameters.
- **FE-21** — Every failure the server reports is shown as a readable message in a toast region. The client never displays a raw JSON error object or an HTTP status code.
- **FE-22** — The client stores nothing sensitive in `localStorage`. The session is an `HttpOnly` cookie the client cannot read, which is what it needs to be for the browser test to prove the key is isolated.
- **FE-23** — The page degrades without JavaScript only to the point of showing a "FitLab needs JavaScript" notice. There is no no-JavaScript fallback, and none is claimed.
- **FE-24** — The layout is usable at 360 px width. The three option cards stack vertically below 900 px.
- **FE-25** — Each option card has a collapsible **attempt log** built from `critique_history`: one row per attempt with its overall score and `retry_reason`, so the user can see the critique-and-retry loop that produced the final image.
- **FE-26** — Remixed looks accumulate in a **revisions strip** for the current session only. The strip lives in client memory, needs no extra API, and is cleared on reload. Every revision can be saved with `POST /api/looks`.
- **FE-27** — Saved looks can be viewed and deleted (with a confirmation step). They cannot be renamed or put into folders in the first version.
- **FE-28** — The critique model is **not** user-selectable in the UI. The server default is used, and each card displays the `critique_model` that produced its critique.

#### Visual design (decided 2026-10-26)

| Concern | Decision |
|---|---|
| Theme | Light "lab notebook": paper background `#F7F7F4` with a faint 24 px graph-paper grid, ink `#111`, white panels with 1 px hairline borders, no heavy shadows |
| Accent | Lab teal (about `#0E8C8C`) for primary actions, focus rings, and passing readouts. Amber for scores below 70 and the unresolved banner. Red only for critical mismatches and errors |
| Typography | IBM Plex Sans (body) and IBM Plex Mono (section labels, scores, codes, timestamps), self-hosted as woff2 in `static/fonts/` under the OFL. No CDN, per SEC-2 |
| Layout | Split workbench: a sticky left controls column (brief, location and weather, wardrobe, Generate) and a right results column (options, revisions, remix). Saved looks open in a slide-out drawer. Columns stack below 900 px |
| Lab metaphor | Subtle. It comes from the visuals (mono `01 / BRIEF` labels, option cards lettered A/B/C, instrument-style readouts). Labels stay plain words, and the user-facing messages in this spec are used verbatim |
| Score display | A large mono overall readout plus one horizontal bar per dimension, with a tick mark at 70 (the retry threshold). A dimension that was not assessed is a hatched bar labeled "Not assessed", never 0 and never a percentage (FE-14) |
| Motion | While a job runs, placeholder cards show a slow scan-line shimmer and a mono elapsed timer. All animation is disabled under `prefers-reduced-motion` |

#### Failure handling

| Failure | Handling |
|---|---|
| `GET /api/auth/me` returns 401 | Open the auth dialog; the client does not retry in a loop |
| The brief form is incomplete | The generate button is disabled and the missing field is marked; the server's 422 is a backstop, not the primary guard |
| A poll returns 404 | The client stops polling and shows "that request is no longer available" |
| A poll returns a network error | The client retries the next tick, up to 5 consecutive failures, then stops and shows a failure toast |
| The job fails server-side | The client shows the server's `error` sentence verbatim |
| An upload fails validation | The server's `reason` is shown next to that tray item; other items are unaffected |
| The image fails to load in the showcase | A placeholder with the score and the critique text is shown; the critique is never hidden because an image failed to render |
| An image is very large on screen | The client scales it with CSS; the underlying bytes are not re-encoded in the browser |

---

## 4. End-to-end workflow

### 4.1 The generate → critique → retry loop

```
Client                    app.py            weather.py      generator.py     critique.py
  |  POST /api/outfits/generate
  |-------------------------->|
  |                            |--- resolve_weather(date,time,city/lat/lon)--->|
  |                            |<-- summary or available=false ----------------|
  |                            |--- build_prompt(brief, weather) --------------->|
  |                            |--- generate_options(...) x3 (concurrent) ------>|
  |                            |<-- 3 images + piece lists ---------------------|
  |                            |=== for each option, independently =============|
  |                            |     critique_image(image, brief, weather, refs)->|
  |                            |<-- critique JSON, retry_recommended ------------|
  |                            |     if retry_recommended and attempts < 3:
  |                            |        build retry prompt from mismatches
  |                            |        generate_image() ----------------------->|
  |                            |        critique_image() ----------------------->|
  |                            |     else: unresolved = open mismatches
  |  GET /api/outfits/{job_id} (poll every 2s)
  |-------------------------->|
  |<-- status + 3 options + critiques + weather ------------------|
```

The three options are critiqued independently; a retry of option 1 does not delay or alter options 2 and 3, and a failure in option 2 does not cause options 1 and 3 to be regenerated.

### 4.2 The remix flow

A remix is a generation with a different brief. It reuses the brief's occasion, aesthetic, styling preference, and event weather unless the user changed them; it adds the selected pieces, the pieces to preserve, and the user's written instructions; it runs the same critique-and-retry loop; and it starts with a **fresh retry budget** (a remix is a new look, not a continuation of the source option's budget).

### 4.3 State machine for a look

```
generated → critiqued → (pass) ────────────────────────→ final
                 │
                 └── (retry_recommended and retries_left > 0) → regenerating → critiqued → …
                 └── (retry_recommended and retries_left = 0) → final_with_unresolved
                 └── (critique transport failure) ─────→ final_without_critique
```

---

## 5. Security and provenance

- **SEC-1** — No API key is ever written to the front end, to a database row, to a log line, to an exception message, or to a crash report. `GET /api/health` exposes only booleans.
- **SEC-2** — The browser makes requests to exactly one origin: the app's own. The Playwright test asserts this over a full generate flow.
- **SEC-3** — Passwords are hashed with bcrypt or Argon2id (DB-3).
- **SEC-4** — Sessions are opaque random tokens, stored server-side, `HttpOnly`, `SameSite=Lax`, `Secure` in production, 30-day expiry.
- **SEC-5** — All SQL is parameterized.
- **SEC-6** — Uploaded files are validated on three axes: MIME type sniffed from the bytes (not the client's `Content-Type`), size (≤ 10 MB), and decodability as an image. The stored filename is generated by the server and never derived from the client's filename.
- **SEC-7** — The upload pre-flight check (clothing-only rule) runs a vision model on the uploaded image and rejects photos containing a person. This is a courtesy check against the course rule, not a security control; it is described honestly as such in `ANNOTATION.md`.
- **SEC-8** — Generated media carries provenance in the prompt and in the saved record: the model slug, the exact prompt, the seed, the generation timestamp, and the statement that the image depicts a fictional mannequin with no real person.
- **SEC-9** — The `.gitignore` excludes `.env`, `*.db`, `*.db-wal`, `*.db-shm`, `uploads/`, and `renders/`. A key in any commit is treated as compromised, so the exclusion is checked in CI before any push.

---

## 6. Testing strategy

| Test file | Scope | Needs a key? | Needs a network? |
|---|---|---|---|
| `tests/test_weather.py` | Coordinate lookup, city override, out-of-range handling, provider error, network error, missing-weather fallback, timezone handling | No | No — the HTTP client is injected and mocked |
| `tests/test_db.py` | Ownership isolation (user A cannot read user B's rows), password hashing, session expiry, idempotent `init_db`, duplicate-username handling, saved-look round trip | No | No — an in-memory or temp-file SQLite database |
| `tests/test_critique.py` | Payload parsing, schema validation, rubric weighting, mismatch detection, retry triggers, retry ceiling, uncertainty disclosure, the reasoning-off request flag | No | No — the HTTP client is injected and mocked |
| `tests/test_browser.py` | Key isolation in source and in the network trace, UI element rendering, generation trigger, request inspection, authentication enforcement | No (the test starts `dev_server.py`, an in-memory stub that implements the Section 3.1 API with fake images and critiques) | No |
| `eval.py` | Cheap-versus-strong critique comparison on real generated outfits, with latency, cost, and agreement recorded in `CHECKS.md` | **Yes** | Yes — this is the one billed script |

The four `pytest` files run with **no API key and no network access**, which is what makes them usable in a pull-request check. `eval.py` is the only script that spends money, and it is run manually and its output is committed to `CHECKS.md`.

The critique contract in Section 7 is written so that `tests/test_critique.py` can assert against it field by field.

---

## 7. Critique JSON contract (normative)

**This section is the contract.** The critique model is instructed to produce exactly this document; `critique.py` validates it; `tests/test_critique.py` asserts it. Any change here is a change to the contract and requires updating the prompt, the validator, and the tests together.

### 7.1 The document

```json
{
  "schema_version": "1.0",
  "attempt": 1,
  "model": "xiaomi/mimo-v2.6-flash",
  "scores": {
    "occasion": 85,
    "aesthetic": 78,
    "styling": 90,
    "weather": null,
    "upload_fidelity": null
  },
  "overall": 84,
  "summary": "The look reads as smart-casual and suits the dinner. The palette is neutral and the layering suits the temperature.",
  "matches": [
    "Silhouette reads as smart rather than business formal, matching the requested aesthetic.",
    "Trousers and knitwear are in a consistent neutral palette."
  ],
  "mismatches": [
    {
      "code": "AESTHETIC_MISMATCH",
      "severity": "minor",
      "affected_pieces": ["p1"],
      "explanation": "The heavy lugged boots read more rugged than the requested clean, relaxed style."
    }
  ],
  "uncertainty": [
    "The image cannot establish the warmth of the outer layer; fabric weight is not visible."
  ],
  "weather_assessed": false,
  "upload_fidelity_assessed": false,
  "retry_recommended": false,
  "retry_reason": ""
}
```

### 7.2 Every field, its type, and whether it is required

| Field | Type | Required | Constraints |
|---|---|---|---|
| `schema_version` | string | yes | Must equal `"1.0"` |
| `attempt` | integer | yes | ≥ 1. The 1-based attempt number for this look |
| `model` | string | yes | The model slug that produced the critique. Overwritten by the server with the actual slug used. |
| `scores` | object | yes | Contains exactly the five keys in 7.3 |
| `scores.occasion` | integer | yes | 0–100 inclusive. Suitability for the brief's occasion |
| `scores.aesthetic` | integer | yes | 0–100 inclusive. Match to the requested aesthetic |
| `scores.styling` | integer | yes | 0–100 inclusive. Match to the requested styling preference |
| `scores.weather` | integer or null | yes (key must exist) | 0–100 inclusive, or `null` when weather is unavailable. `null` exactly when `weather_assessed` is `false` |
| `scores.upload_fidelity` | integer or null | yes (key must exist) | 0–100 inclusive, or `null` when no reference image was supplied. `null` exactly when `upload_fidelity_assessed` is `false` |
| `overall` | integer | yes (computed server-side) | 0–100 inclusive. See 7.4 for the exact formula |
| `summary` | string | yes | 1–3 sentences, 1–600 characters |
| `matches` | array of strings | yes | 0–8 entries, each 1–300 characters |
| `mismatches` | array of objects | yes | 0–8 entries, each an object with the four fields in 7.5 |
| `uncertainty` | array of strings | yes | 0–8 entries, each 1–300 characters |
| `weather_assessed` | boolean | yes | `true` iff weather was available and `scores.weather` is an integer |
| `upload_fidelity_assessed` | boolean | yes | `true` iff at least one reference image was supplied and `scores.upload_fidelity` is an integer |
| `retry_recommended` | boolean | yes | See 7.6. **Computed server-side.** |
| `retry_reason` | string | yes | Empty string when `retry_recommended` is `false`; otherwise a one-sentence explanation naming the trigger |

### 7.3 Score scale

- **Scale:** integers from **0 to 100 inclusive**, no decimals, no negative values, no values above 100.
- **Meaning:** the score is the model's assessment of **how well the image satisfies the corresponding part of the brief** — not a measure of fashion quality, not a probability, and not a confidence interval. This wording is in the prompt and in the UI.
- **Dimension definitions:**

| Dimension | The question it answers |
|---|---|
| `occasion` | Is this outfit at the right formality and appropriateness for the stated occasion? |
| `aesthetic` | Does this outfit deliver the requested aesthetic (the mood and appearance the user asked for)? |
| `styling` | Does this outfit match the requested styling preference (for example masculine, feminine, unisex)? |
| `weather` | Is this outfit suitable for the measured conditions at the event time and place? **Assessed only when a forecast exists.** |
| `upload_fidelity` | Does the generated outfit preserve the visible colors, patterns, shape, and distinguishing details of the selected reference garments? **Assessed only when reference images were supplied.** |

- **A dimension that was not assessed is `null`.** It is never 0. A `null` dimension is displayed as "Not assessed" and is excluded from the weighted total.

### 7.4 The overall score, computed server-side

Weights, as integers summing to 100:

| Dimension | Weight |
|---|---|
| `occasion` | 30 |
| `aesthetic` | 25 |
| `styling` | 20 |
| `weather` | 15 |
| `upload_fidelity` | 10 |

**Rule.** Take the set of **assessed** dimensions — those whose score is an integer, which is always `occasion`, `aesthetic`, and `styling`, plus `weather` when `weather_assessed` is true, plus `upload_fidelity` when `upload_fidelity_assessed` is true.

```
overall = round_half_up( sum(weight_i * score_i for i in assessed) / sum(weight_i for i in assessed) )
```

The denominator is the sum of the weights of the assessed dimensions only. Worked examples, all of which `tests/test_critique.py` asserts:

| Assessed scores | Denominator | `overall` |
|---|---|---|
| occasion 85, aesthetic 78, styling 90 | 75 | `round_half_up((30·85 + 25·78 + 20·90) / 75)` = `round_half_up(6300 / 75)` = `round_half_up(84.0)` = **84** |
| occasion 85, aesthetic 78, styling 90, weather 52 | 90 | `round_half_up((6300 + 15·52) / 90)` = `round_half_up(7080 / 90)` = `round_half_up(78.666…)` = **79** |
| occasion 80, aesthetic 80, styling 80, weather 80, upload_fidelity 80 | 100 | `round_half_up(8000 / 100)` = **80** |

`round_half_up` rounds to the nearest integer, with `.5` going up. The server always computes this value and always overwrites whatever the model returned. If the model returned an `overall` that differs from the computed value by more than 1, the document is a **validation failure** (`status = "failed"`); a difference of exactly 1 is tolerated and overwritten.

### 7.5 A mismatch object

| Field | Type | Required | Constraints |
|---|---|---|---|
| `code` | string | yes | One of the enum below |
| `severity` | string | yes | One of `"minor"`, `"major"`, `"critical"` |
| `affected_pieces` | array of strings | yes | 0–6 piece ids or names from the option's piece list |
| `explanation` | string | yes | 1–500 characters, plain language, describes what is visibly wrong |

**Severity definitions**, quoted into the prompt:

| Severity | Meaning | Triggers a retry? |
|---|---|---|
| `minor` | A small deviation that does not change whether the look suits the brief | **No** |
| `major` | A clear departure from the brief that a user would notice and want fixed | **Yes** |
| `critical` | The look does not satisfy a core requirement of the brief — for example the wrong occasion entirely, or a selected uploaded garment is visibly absent or replaced | **Yes** |

**`code` enum:**

`WRONG_OCCASION`, `WRONG_FORMALITY`, `AESTHETIC_MISMATCH`, `STYLING_PREFERENCE_MISMATCH`, `WEATHER_UNSUITABLE`, `UPLOAD_FIDELITY_BREACH`, `MISSING_EXPECTED_PIECE`, `EXTRA_UNEXPECTED_PIECE`, `ILLEGIBLE_IMAGE`.

An unknown `code` value is a **validation failure**. An unknown `severity` value is a **validation failure**.

### 7.6 The retry trigger, exactly

```
retry_recommended = (overall < 70) OR (any(m.severity in {"major", "critical"} for m in mismatches))
```

- `overall < 70` is **strictly less than**. An `overall` of exactly 70 does **not** trigger on score alone.
- A `minor` mismatch does **not** trigger on its own.
- A `null` weather score does **not** trigger. **Missing weather alone never triggers a retry.**
- A `null` upload-fidelity score does **not** trigger, for the same reason.
- The rule is evaluated by `critique.py` on the **server-computed** `overall` and the validated `mismatches`. The model is instructed to apply the same rule, and the server's value is authoritative in both directions: if the model says `retry_recommended: true` without a qualifying trigger, the server sets it to `false`; if the model says `false` while a trigger applies, the server sets it to `true`.
- `retry_reason` is filled by the server with a short sentence naming which branch fired, e.g. `"overall 64 is below the 70 threshold"` or `"one major mismatch: UPLOAD_FIDELITY_BREACH"`.

### 7.7 Worked examples of the trigger

| `overall` | Worst mismatch severity | `retry_recommended` | Reason |
|---|---|---|---|
| 92 | minor | `false` | — |
| 70 | minor | `false` | 70 is not below 70, and minor does not trigger |
| 69 | minor | `true` | 69 < 70 |
| 92 | major | `true` | major mismatch |
| 64 | critical | `true` | both branches fire; the score branch is named first |
| 88 | none, weather `null` | `false` | missing weather alone never triggers |

### 7.8 The failure document

When validation fails, the server does not show a partial critique. It emits this to the client instead, so the client has one shape to render:

```json
{
  "status": "failed",
  "error": "invalid_response" | "provider_error" | "rate_limited" | "timeout",
  "model": "xiaomi/mimo-v2.6-flash",
  "attempt": 1,
  "raw_excerpt": null
}
```

`raw_excerpt` is `null` in every response that reaches the client; the raw model text is logged server-side only, so a malformed or unexpected model output is never rendered in the user's browser.

---

## 8. Consolidated failure matrix

| # | Failure | Detected in | System state afterwards | What the user sees |
|---|---|---|---|---|
| F1 | `OPENROUTER_API_KEY` missing or invalid | `generator.py` / `critique.py` on first call | Job `failed` | "The styling service is not configured right now." |
| F2 | OpenRouter rate limit (429) | `generator.py` / `critique.py` | That option or critique fails; other options continue | "The image service is busy right now." |
| F3 | OpenRouter 5xx or timeout | `generator.py` / `critique.py` | Same | "The image service did not respond properly." |
| F4 | Image model returns a response with no image | `generator.py` | That option fails | "One of the three outfit ideas could not be drawn." |
| F5 | Critique model returns unparseable JSON | `critique.py` (CRT-3) | Option returned with `status = "failed"`; **no retry burned** | "We could not check this outfit against your brief." |
| F6 | Critique model returns schema-invalid JSON | `critique.py` (CRT-4) | Same | Same |
| F7 | Retry ceiling reached with mismatches open | `critique.py` (CRT-12) | `retry_exhausted = true`, `unresolved` populated | The image, the scores, and an explicit unresolved-issues list |
| F8 | Forecast out of the provider's window | `weather.py` (WX-5) | `available = false`; generation continues | "Generated without weather guidance." |
| F9 | Weather provider error or network failure | `weather.py` (WX-6) | `available = false`; generation continues | Same |
| F10 | City not found | `weather.py` (WX-7) | `available = false`; generation continues | "We could not find that city." |
| F11 | Upload contains a person | `app.py` upload pre-flight | Nothing stored | "That photo looks like it shows a person. Please upload clothing only." |
| F12 | Upload is the wrong type, too large, or undecodable | `app.py` | Nothing stored | "That file is not a usable image (max 10 MB)." |
| F13 | Unauthenticated request to a protected endpoint | `app.py` middleware | Nothing happens | "Please sign in again." |
| F14 | Request for another user's resource | `db.py` (DB-2) | Nothing happens | 404, "not found" |
| F15 | Database locked or disk error | `db.py` | Transaction rolled back | "We could not save that right now." |
| F16 | Duplicate username | `db.py` | Nothing written | "That username is taken." |
| F17 | Wrong username or password | `app.py` | Nothing written | "That username and password do not match." |
| F18 | Client poll hits a deleted or unknown job | `app.py` | Nothing happens | "That request is no longer available." |
| F19 | Job still running after the client gives up | `app.py` | The job continues; the result is still savable from the looks drawer | "This is taking longer than usual. You can find the result in your saved looks." |
| F20 | Review service returns a score the rubric cannot accept | `critique.py` (CRT-5) | Option returned with `status = "failed"` | "We could not check this outfit against your brief." |

**Cross-cutting rule.** No failure in this table is allowed to (a) invent data, (b) present an unassessed dimension as a score, (c) present an unresolved look as a pass, (d) present unavailable weather as a forecast, or (e) leak a secret. These five are the project's non-negotiables and each maps to a specific behavior number.

---

## 9. Cost estimate

### 9.1 Unit prices (verified 2026-10-25)

| Service | Unit | Price |
|---|---|---|
| `google/gemini-3.1-flash-image` — prompt | per Mtok | $0.50 |
| `google/gemini-3.1-flash-image` — text completion | per Mtok | $3.00 |
| `google/gemini-3.1-flash-image` — output image | derived per image | **$0.077** (0.00006 × ~1,290 image tokens) |
| `google/gemini-3-pro-image` (alternative) — output image | derived per image | **$0.134** (0.00012 × ~1,120 image tokens) |
| `google/gemini-3.1-flash-lite-image` (alternative) — output image | derived per image | **$0.039** (0.00003 × ~1,290 image tokens) |
| `xiaomi/mimo-v2.6-flash` — prompt | per Mtok | $0.14 |
| `xiaomi/mimo-v2.6-flash` — completion | per Mtok | $0.28 |
| `minimax/minimax-m3` — prompt | per Mtok | $0.30 |
| `minimax/minimax-m3` — completion | per Mtok | $1.20 |
| `openai/gpt-4o-mini` (alternative) | per Mtok | $0.15 / $0.60 |
| `minimax/minimax-01` (alternative) | per Mtok | $0.20 / $1.10 |
| `anthropic/claude-sonnet-5.5` (alternative strong) | per Mtok | $2.00 / $10.00 |
| Open-Meteo forecast and geocoding | per request | **$0.00** (no key) |

Token assumptions, stated so they can be checked: an input image at 1024 px is ~1,100 input tokens; an output image bills as ~1,290 (Flash) or ~1,120 (Pro) output tokens, charged at the model's `image_output` rate rather than at the text-completion rate; a critique prompt is ~900 text tokens; a critique JSON completion is ~700 tokens.

### 9.2 Cost of one critique call

| Configuration | Cheap (`mimo-v2.6-flash`) | Strong (`minimax-m3`) | Frontier (`claude-sonnet-5.5`) |
|---|---|---|---|
| Generated image only | ~$0.00048 | ~$0.00144 | ~$0.0110 |
| + 3 reference images | ~$0.00094 | ~$0.00243 | ~$0.0176 |

### 9.3 Cost of one generate request

Worst case is 3 options × 3 attempts (initial + 2 retries) = 9 images and 9 critiques.

| Scenario | Image cost | Piece-identification cost | Critique cost (cheap) | Critique cost (strong) | **Total (cheap)** | **Total (strong)** |
|---|---|---|---|---|---|---|
| **Typical** — 3 options, no retries | 3 × $0.077 = $0.231 | ~$0.001 | ~$0.0014 | ~$0.0043 | **$0.234** | **$0.236** |
| **Worst case** — all 3 options retry twice | 9 × $0.077 = $0.693 | ~$0.003 | ~$0.0043 | ~$0.0130 | **$0.700** | **$0.709** |
| **Worst case with 3 references** | 9 × $0.077 = $0.693 | ~$0.003 | ~$0.0085 | ~$0.0219 | **$0.705** | **$0.718** |
| **Expensive-model variant** — `gemini-3-pro-image`, typical | 3 × $0.134 = $0.402 | ~$0.003 | ~$0.0014 | ~$0.0043 | **$0.406** | **$0.409** |

### 9.4 The finding that matters

**The critique model choice is nearly free; the image model is the entire cost.** Switching the critique from the cheap model to the strongest model we considered (`claude-sonnet-5.5`, 14× the input price and 36× the output price) adds about **$0.10 per worst-case request** — roughly **12% of that request's total**. Meanwhile the image model is 90–95% of every request's cost.

The consequence for the design: the cheap model is the default because it is the right call at the volume we run, but the expensive model is affordable per request, so the strong model is used (a) as the reference judgment in `eval.py`, (b) as the escalation path if the cheap model proves weak on upload fidelity, and (c) optionally per-request for users who want the higher-quality review. The project is not cost-constrained by the critique at all, and the spec says so rather than implying that model shopping saved the project money.

### 9.5 Project-level estimate

| Item | Assumption | Cost |
|---|---|---|
| Development and demo requests | 30 requests, mixed typical/worst case, ~50/50 | **$14.01** |
| `eval.py` — outfit generation for the benchmark set | 12 images + 12 piece-identification calls | **$0.93** |
| `eval.py` — cheap model over the benchmark set | 12 critiques × 2 repeats = 24 calls | **$0.01** |
| `eval.py` — strong model over the benchmark set | 24 calls | **$0.03** |
| `eval.py` — frontier model over the benchmark set | 24 calls | **$0.26** |
| Open-Meteo | unlimited, no key | **$0.00** |
| Render web service | Free tier (spins down when idle) | **$0.00** |
| Render persistent disk for SQLite | 1 GB free tier | **$0.00** |
| **Project total** | | **≈ $15.24** |

This sits under the $20 threshold the assignment names, with no explanation required. If the team demos more heavily than 30 requests, the image generation dominates and the total rises roughly $0.23 per additional typical request; a 60-request project would land near $28 and would need the stated justification. `README.md` carries a running total updated from the OpenRouter usage page, as the assignment requires, and `CHECKS.md` carries the per-run cost ledger.

### 9.6 Cost-control mechanisms, and their cost

| Mechanism | Effect | Cost |
|---|---|---|
| Retry ceiling of 2 (CRT-12) | Caps a request at 9 images instead of unbounded | Saves an unbounded tail |
| No self-retry in the generator (GEN-7) | A failed image call is not re-billed | Saves 1–3 images per transient failure |
| No retry on a failed critique (CRT-17) | A transport failure does not trigger image regeneration | Saves up to 6 images per provider outage |
| Weather caching (WX-11) | One forecast per job instead of one per poll | Saves provider load, no dollar cost |
| `xiaomi/mimo-v2.6-flash` as the default critic | 2.1×/4.3× cheaper than `minimax/minimax-m3` | ~$0.009 saved per worst-case request |
| Per-attempt usage logging (CRT-18) | Makes the ledger in `CHECKS.md` and `README.md` derivable rather than guessed | No cost |

---

## 10. Traceability

| Intent | Component | Behaviors | Verified by |
|---|---|---|---|
| `accounts.md` | App server (3.1), Database (3.2) | APP-3, APP-5, APP-6, DB-2, DB-3, DB-4, DB-5 | `tests/test_browser.py` (auth enforcement), `tests/test_db.py` (ownership isolation) |
| `clothing-uploads.md` | App server (3.1), Generator (3.4), Critique (3.5) | APP-11, GEN-4, GEN-9, CRT-2, CRT-7, CRT-11 | `tests/test_critique.py` (fidelity dimension), `tests/test_browser.py` (upload flow) |
| `event-weather.md` | Weather (3.3) | WX-1 … WX-11 | `tests/test_weather.py` |
| `outfit-generation.md` | Generator (3.4), Critique (3.5) | GEN-1, GEN-2, GEN-3, GEN-11, CRT-10, CRT-12 | `tests/test_critique.py`, `eval.py` |
| `outfit-remixing.md` | Generator (3.4), App server (3.1), Critique (3.5) | GEN-9 (revision line), CRT-14 | `tests/test_critique.py`, `tests/test_browser.py` |
| `saved-looks.md` | Database (3.2), App server (3.1), Front end (3.6) | DB-8, DB-9, DB-10, APP-6, FE-19, FE-20 | `tests/test_db.py`, `tests/test_browser.py` |
| `visual-critique.md` | Critique (3.5) | CRT-1 … CRT-20, Section 7 | `tests/test_critique.py` |
| `team-project-1.md` (key-on-server) | App server (3.1), Front end (3.6) | APP-2, SEC-1, SEC-2, FE-22 | `tests/test_browser.py` |
| `team-project-1.md` (cheap vs strong) | Critique (3.5), Section 9 | CRT-19, Section 9.2–9.5 | `eval.py`, `CHECKS.md` |

### 10.1 Changes this specification requires in `plan.md`

`plan.md` was written on 2026-10-19 and named four model slugs that no longer exist. Before the build starts, `plan.md` must be amended as follows:

1. `generator.py` row: `black-forest-labs/flux-1-schnell` and `recraft/recraft-v3` → **`google/gemini-3.1-flash-image`**, with `google/gemini-3-pro-image` as the evaluated alternative. Both original slugs are unreachable, and neither could have done image-conditioned generation, so the upload-fidelity feature required a different provider family anyway.
2. `critique.py` row: `openai/gpt-4o-mini` and `minimax/minimax-01` → **`xiaomi/mimo-v2.6-flash`** (cheap) and **`minimax/minimax-m3`** (strong).
3. Proof section: `anthropic/claude-3.5-sonnet` and `google/gemini-pro-vision` → **`anthropic/claude-sonnet-5.5`** and **`minimax/minimax-m3`**.
4. Add to the `critique.py` row: the requirement that MiMo calls set `reasoning: {"enabled": false}` (CRT-3 and the reasoning note in Section 3.5), and that the critique JSON contract in Section 7 is normative for `tests/test_critique.py`.
5. `eval.py` row: the benchmark pair is `xiaomi/mimo-v2.6-flash` against `minimax/minimax-m3`, with `openai/gpt-4o-mini` retained as the third point that `plan.md` originally committed to.
6. Files table: add **`tests/test_db.py`**, which `plan.md` does not currently list but Section 10's traceability depends on. Ownership isolation and password hashing are two of the four success criteria in `intent/accounts.md` ("Users cannot access another user's private saved looks or uploads"), and they are only meaningfully testable at the data layer, not from the browser.

---

**Prepared by:** Claude Code, for the FitLab team (Gabriel, Nadia, Patrick)
**Review required before build:** every component's language and model decision needs a named team member's sign-off, and Section 7 needs a second reader who will write `tests/test_critique.py` against it.

Approved by: Nadia (pending team review), 2026-10-25


## Backend implementation amendment

The backend implementation adds `services.py` for orchestration, `provider.py` for HTTP transport,
`media.py`/`limits.py` for image validation and request limits, and `models.py` for HTTP schemas.
`app.py` remains free of SQL and direct external-provider calls. SQLite is the authoritative job
state; the process retains task handles, not a second mutable copy of each job. Run one worker.

The current OpenRouter image API is `POST /api/v1/images`, with `input_references` and base64
image results, rather than the older chat-based generation transport described above.
The default model's dedicated endpoint does not advertise seed support. Fresh variation identifiers
are included in prompts, stored as `variation_id`; `seed` is null when unsupported. This supersedes
GEN-10/CRT-16's assertion of an applied seed for this endpoint. Provider documentation:
https://openrouter.ai/docs/guides/overview/multimodal/image-generation

Wardrobe and saved-look responses include authenticated `image_data_url` values. Images are stored
under private `uploads/` and `renders/` directories, not mounted as public static files. Critique
results are exposed directly as the section 7 document, with per-call usage/latency metadata, rather
than leaking the internal result wrapper into the frontend contract. Missing reported cost is null.

The upload endpoint enforces a 10 MB file limit. A pre-parser middleware bounds the entire multipart
request to 10 MB plus 64 KB overhead, including chunked requests, before parser spooling. Image bytes
are validated before persistent storage. Photos with people, non-clothing images, and inconclusive
preflight calls are not saved. Notes accept up to 1000 characters, matching the shipped frontend.

A remix validates piece objects against the owned completed source job and supplies its relevant
outfit images as generation references. Only actual wardrobe images count toward upload-fidelity
scoring. Unchanged event context reuses the original forecast. Saved-look date filters apply to event
dates, and snapshots preserve original critiques, weather, and generation provenance.

Admission is limited to two active jobs per user and three executing jobs per process. Database
connections use a five-second SQLite busy timeout; they do not perform the earlier proposed three
application-level retries. Interrupted jobs become failed on startup. Render files remain while
source jobs reference them, even after a saved-look entry is deleted; retention cleanup is not yet implemented.
