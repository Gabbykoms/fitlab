# FitLab backend

This is the backend development guide. The authoritative contracts are in [spec.md](spec.md), especially sections 3.1–3.5, 5, and 7; implementation responsibilities and sequencing are in [plan.md](plan.md).

## Current status

The repository currently runs a frontend preview against `dev_server.py` and `dev_fixtures.py`. This API uses in-memory data and fake images and critiques. It does not provide production authentication, persistent storage, real weather, or AI generation.

The first backend slice is implemented in `app.py` and `db.py`: static serving, database health, registration, login, logout, and session enforcement. Accounts and sessions persist in SQLite. Styling services and their database tables remain planned; authenticated requests to unimplemented API routes return `501`. Existing browser tests still exercise the preview server; `tests/test_app.py` checks the real accounts API.

## Modules

| File | Responsibility |
|---|---|
| `app.py` | FastAPI routes, request validation, session enforcement, orchestration, background jobs, and serving `static/`. No SQL or direct provider calls. |
| `db.py` | SQLite schema and all parameterized SQL, transactions, sessions, and ownership checks. No network calls. |
| `weather.py` | Resolve event-time forecasts through Open-Meteo, including city lookup, timezone handling, and explicit unavailable results. |
| `generator.py` | Build prompts, generate three mannequin outfits with reference images, and identify visible clothing pieces. |
| `critique.py` | Inspect generated images and references, validate critique JSON, and control the bounded retry loop. Independent of the app server and database. |

Target stack: Python 3.11+, FastAPI, Uvicorn, SQLite, and `httpx`. The specification calls for bcrypt or Argon2id password hashing. Add implementation dependencies to `requirements.txt` as the modules land.

## Features and API

All API paths start with `/api`. See spec section 3.1 for exact request and response fields.

| Feature | Routes | Required behavior |
|---|---|---|
| Health | `GET /api/health` | Check database availability; report configuration booleans without exposing secrets. |
| Accounts | `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` | Hashed passwords, opaque session cookies, and expiry after 30 days of inactivity. |
| Wardrobe | `GET /api/wardrobe`, `POST /api/wardrobe/upload`, `DELETE /api/wardrobe/{item_id}` | Validate images, reject people, store category/label, prevent duplicate uploads per user, and enforce ownership. |
| Weather | `GET /api/weather` | Resolve city or coordinates for the event date/time; return an explicit unavailable summary on failure. |
| Generation | `POST /api/outfits/generate`, `GET /api/outfits/{job_id}` | Submit a background job and poll for three outfit options with pieces, critiques, and weather. |
| Remix | `POST /api/outfits/remix` | Preserve selected pieces and source context, apply revision instructions, and start a fresh generation/critique job. |
| Saved looks | `POST /api/looks`, `GET /api/looks`, `DELETE /api/looks/{look_id}` | Save the full result and original weather; filter by occasion and event-date range. |

Health, registration, login, and static assets are public. Other routes require a valid session. The server derives the user ID from the session, never from a client-supplied identity. Requests for another user's job return `404`.

## Generation workflow

1. Validate the brief and ownership of selected wardrobe items.
2. Return `202` with a `job_id`; perform the work in the background.
3. Resolve weather in the event location's timezone. A city override takes precedence over coordinates. Missing weather must not stop generation or be replaced with invented conditions.
4. Generate three distinct outfits on fictional, faceless mannequins and identify their visible garments.
5. Critique the actual image pixels against the brief and uploaded references. Score occasion, aesthetic, styling, weather, and upload fidelity using the contract in spec section 7.
6. Retry each option independently when the overall score is below 70 or a major/critical mismatch requires it. Allow at most two retries, for three total attempts per option.
7. Return the final images, piece lists, critique histories, and unresolved issues. A failed critique is disclosed rather than presented as a passing score.

Job states are `queued`, `running`, `complete`, and `failed`. Use in-process asynchronous tasks with job state mirrored in SQLite. Interrupted jobs must become failed after restart instead of remaining pending indefinitely. Redis and Celery are outside the planned architecture.

Remixes reuse this workflow with a fresh retry budget. Model choices and provider request details belong in the spec; verify provider availability when implementing those calls.

## Persistence and safety

- Store users, sessions, wardrobe metadata, jobs, saved looks, and settings in SQLite. Use transactions, foreign-key enforcement, WAL mode, and parameterized SQL.
- Scope user-owned data access to the authenticated user in both routes and database helpers.
- Validate uploaded bytes for image type and decodability, enforce the 10 MB limit, generate storage filenames server-side, and run the clothing-only vision check.
- Keep uploads and generated renders outside public static assets. The frontend receives images through authenticated API responses.
- Use `HttpOnly`, `SameSite=Lax` session cookies, with `Secure` in production.
- Keep provider secrets in the server environment and out of responses, logs, database records, and browser assets.
- Preserve the original weather and validated critique when saving a look. Store generation provenance: model, prompt, seed where available, timestamp, and fictional-mannequin disclosure.
- On deployment, persist the database, uploads, and renders across restarts. These files are ignored by Git.

## Frontend integration points

- The browser calls only same-origin `/api/*` routes and polls jobs every two seconds.
- Outfit options contain `image_data_url`. The implemented wardrobe and saved-look views expect that field too; make those response shapes explicit when implementing their endpoints.
- The critique module's result wrapper contains `payload` plus operational metadata. The HTTP outfit response must expose the section 7 critique document where the frontend expects `option.critique`, with history normalized the same way.
- Remix requests currently send `city` but not coordinates. Reuse the source job's location when no replacement city is supplied.
- Unassessed dimensions are `null` with the appropriate assessment flags, not zero scores. Error responses and failed jobs need readable messages.

## Local development

Run these commands from the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
```

The preview is available now and needs no API keys:

```bash
.venv/bin/uvicorn dev_server:app --reload
# Open http://localhost:8000
```

Run the real accounts backend on a separate port from the mock preview:

```bash
.venv/bin/uvicorn app:app --reload --port 8001
```

| Environment variable | Planned use |
|---|---|
| `OPENROUTER_API_KEY` | Server-side AI provider authentication. Configure before real generation or critique calls. |
| `FITLAB_SECURE_COOKIES` | Set to `true` in HTTPS deployments, including behind a TLS proxy. HTTPS requests also enable Secure cookies automatically. |
| `FITLAB_DB_PATH` | Database location; defaults to `./fitlab.db`. Point to persistent storage in deployment. |

Open-Meteo is specified as keyless for the initial implementation. A `.env` file is ignored by Git, but the project does not currently configure automatic loading of it; supply variables through the process environment.

## Implementation order

1. Add `db.py`, schema initialization, and database tests.
2. Add `app.py` with health, registration, login, logout, current-user routes, session enforcement, and static serving.
3. Implement weather and wardrobe persistence/validation, coordinating the upload vision check with the critique work.
4. Add generation jobs, piece extraction, and the polling contract.
5. Integrate critique and retry handling, checking the existing `critique-checker` branch before duplicating work.
6. Connect remix and saved-look operations.
7. Test the integrated backend, run real model comparisons, document results/costs, and deploy.

Per the plan, Gabriel leads accounts/database and generation; Nadia leads weather and remix; Patrick leads critique, uploads, testing, and deployment. Coordinate changes to shared `app.py` routes before implementing them.

## Verification

The existing browser suite runs against the mock API:

```bash
.venv/bin/pytest tests/test_browser.py -q
```

Run the implemented backend account tests with `.venv/bin/pytest tests/test_app.py -q`. They cover persistence, password hashing, duplicate usernames, session rotation/expiry/logout, authentication enforcement, HTTPS cookies, health failures, and secret-safe validation.

Verification targets as the remaining services land:

| Area | Evidence required |
|---|---|
| Database and accounts | Ownership isolation, password hashing, session expiry, duplicate usernames, idempotent initialization, and saved-look round trips. |
| Weather | Location precedence, timezone/date handling, unavailable forecasts, and provider failures without live network dependencies. |
| Critique | JSON validation, score calculations, mismatch severity, unassessed dimensions, and retry limits using fake providers. |
| API and jobs | Authentication, ownership checks, upload validation, job transitions, restart recovery, and safe failures. |
| Integrated browser flow | Run browser checks against the real app with stubbed providers; retain same-origin/key-isolation assertions. |
| Real model evaluation | Compare cheap and stronger vision models on project images, recording accuracy, latency, and billed cost. |

Record verification in `CHECKS.md`, development conventions in `CLAUDE.md`, component explanations in `ANNOTATION.md`, and the required separate review in `REVIEW.md` as those artifacts are created. Keep the root README's deployment URL and cost total current.
