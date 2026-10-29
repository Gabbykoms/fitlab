# FitLab backend

The real backend now implements accounts, wardrobe uploads, weather lookup, background outfit generation, visual critique/retries, remixing, and saved looks. The full contracts are in [spec.md](spec.md); implementation notes below explain refinements made during integration.

Offline tests verify the real API and storage with fake external providers. Live AI output quality, billed model comparisons, and deployment still require verification. `dev_server.py` remains a separate, in-memory UI preview.

## Modules

| File | Responsibility |
|---|---|
| `app.py` | FastAPI routes, session middleware, validation, health, static serving, and service wiring. |
| `db.py` | SQLite schema, transactions, sessions, ownership-scoped wardrobe/jobs/looks queries, and restart recovery. |
| `services.py` | Background jobs, upload orchestration, remix context, private storage, and response serialization. |
| `models.py` | Typed request contracts and field validation. |
| `weather.py` | Open-Meteo geocoding and event-local hourly forecasts, with explicit unavailable results. |
| `generator.py` | Prompts, mannequin generation, image validation, and vision-based garment extraction. |
| `critique.py` | Strict critique parsing/scoring, image-based critique calls, upload preflight, and the three-attempt ceiling. |
| `provider.py` | OpenRouter HTTP transport and safe provider failures. |
| `media.py`, `limits.py` | Image decoding, private filesystem storage, and bounded multipart uploads. |
| `eval.py` | Explicitly invoked, billed comparison of vision models against existing image cases. |

The critique parser and its original tests were imported from `origin/critique-checker` at `a8674d6`, then extended with provider integration. They were reused rather than independently reimplemented.

## API

| Feature | Routes |
|---|---|
| Health | `GET /api/health` |
| Accounts | `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me` |
| Wardrobe | `GET /api/wardrobe`, `POST /api/wardrobe/upload`, `DELETE /api/wardrobe/{item_id}` |
| Weather | `GET /api/weather` |
| Generation | `POST /api/outfits/generate`, `GET /api/outfits/{job_id}` |
| Remix | `POST /api/outfits/remix` |
| Saved looks | `POST /api/looks`, `GET /api/looks`, `DELETE /api/looks/{look_id}` |
| API schema | `GET /api/openapi.json` (authenticated) |

Only health, registration, login, and static assets are public. The session identifies the user; callers cannot choose another user ID. Ownership checks apply to jobs, uploads, source pieces, and saved looks. User-owned resources that are not accessible return `404`.

## Running locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app:app --reload --port 8001
```

Open http://localhost:8001. Accounts, empty galleries, and saved data work without a provider key. Upload preflight and image generation require `OPENROUTER_API_KEY` in the server environment; they fail explicitly when it is absent. The app does not automatically load `.env` files.

| Variable | Use |
|---|---|
| `OPENROUTER_API_KEY` | Server-only provider authentication; read at call time. |
| `FITLAB_DB_PATH` | SQLite file, default `./fitlab.db`. |
| `FITLAB_STORAGE_PATH` | Parent of private `uploads/` and `renders/`; defaults to the database directory. |
| `FITLAB_SECURE_COOKIES` | Set `true` behind an HTTPS reverse proxy. HTTPS requests also enable Secure cookies. |
| `FITLAB_IMAGE_MODEL` | Default `google/gemini-3.1-flash-image`. |
| `FITLAB_CRITIQUE_MODEL` | Default `xiaomi/mimo-v2.6-flash`. |
| `PORT` | Listening port when starting with `python app.py`. |

Open-Meteo needs no key. `WEATHER_API_KEY` is retained only as a health-report compatibility field; it is not used by this implementation.

For the offline mock UI preview, run `.venv/bin/uvicorn dev_server:app --reload` on port 8000. Mock accounts/data are separate from the real app.

## Processing and persistence

1. Validate a brief and load only the caller's selected wardrobe images.
2. Insert a queued job and return `202` with its ID. At most two jobs per account can be active; at most three jobs execute concurrently per process.
3. Resolve weather. A city overrides coordinates; no location or forecast means no weather assessment.
4. Generate three independent mannequin options (one for a remix), then critique their actual pixels. A failing option can be retried twice; a failed critique call does not trigger another image generation.
5. Store private image files and result metadata in SQLite. Partial success keeps the successful options and their original indexes. Missing image files do not hide stored critique text.
6. Poll until complete or failed. Restarted/interrupted jobs become failed rather than remaining pending.
7. Save looks as snapshots of the brief, critique, provenance, and original weather. Date filters use the event date. Deleting a saved-look entry retains its render because the source job still references it.

Remixes validate selected piece objects against the owned completed source job. Source outfit images guide generation; only actual wardrobe uploads are scored for upload fidelity. Source weather is reused if date, time, and location are unchanged. A deleted source wardrobe item must be removed from the brief before it can be reused.

## Provider integration

Image generation uses OpenRouter's dedicated `POST /api/v1/images` API with base64 `input_references`. Vision calls use `/api/v1/chat/completions` with image parts. MiMo reasoning is disabled so the response can be parsed as JSON.

The public catalog was checked during implementation: the default image model accepts image references, and the configured cheap/strong critique models accept images. The dedicated endpoint does not advertise seed control for the default image model. Prompts include a fresh variation identifier; provenance records `seed: null` and `variation_id`, not a falsely applied seed. Changes in model availability must be checked before a live evaluation.

Provider-reported usage is stored with each result. Unreported cost remains `null`, not zero. Reconcile costs against the provider dashboard before updating the project cost total.

Sources: [OpenRouter image API](https://openrouter.ai/docs/guides/overview/multimodal/image-generation), [Open-Meteo forecast API](https://open-meteo.com/en/docs).

## Verification

```bash
.venv/bin/python -m playwright install chromium
.venv/bin/pytest -q
```

- `tests/test_app.py`: persistent accounts, sessions, password hashing, cookies, health, and safe validation.
- `tests/test_db.py`: initialization, transactions, ownership, job admission, and recovery.
- `tests/test_backend.py`: actual API upload/generate/remix/save flows, validation, ownership, partial failures, retry limits, and persistence.
- `tests/test_weather.py`, `tests/test_provider.py`: external request shapes and failure handling using mocked HTTP.
- `tests/test_critique.py`: the inherited normative scoring/validation suite.
- `tests/test_backend_browser.py`: full frontend flow against the real backend and isolated SQLite, with fake AI/weather providers.
- `tests/test_browser.py`: existing mock UI scenarios and regressions.

To perform a **billed** evaluation, prepare a JSON list of cases, each with `image` (local path), `brief`, optional `weather`, and optional `references` (local paths). Then run:

```bash
.venv/bin/python eval.py --cases eval-cases.json --output eval-results.json
```

This compares the default cheap and stronger vision models. Review against human judgments; the script records outputs and reported costs, not an invented accuracy score.

## Deployment

A Dockerfile is included; it has not been deployed or validated with a Docker build in this session. Run a **single worker/service instance**, because jobs and concurrency controls are process-local. Mount persistent storage at `/data` for SQLite and private images. The Dockerfile sets the corresponding paths and secure-cookie flag; supply the provider key through the hosting environment. Use `/api/health` for readiness.

Before releasing: run a paid end-to-end smoke test, compare critique models, reconcile billing, verify storage survives a redeploy, and complete the course's independent review and annotation artifacts. No deployment or paid inference was performed during implementation.
