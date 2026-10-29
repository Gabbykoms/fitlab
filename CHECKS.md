# Backend verification

## 2026-10-29 — remaining backend implementation

- `.venv/bin/pytest -q`: **110 passed**, 2 dependency deprecation warnings, 48.11 seconds.
- After adding an explicit remix reference-count guard: `.venv/bin/pytest tests/test_backend.py tests/test_db.py -q`: **15 passed**, including the new regression. The repository now contains 111 tests; the last full run preceded this one-test addition.
- `git diff --check`: passed.
- Python compilation checks for backend modules: passed.

Coverage includes persistent accounts/sessions, ownership isolation, transaction rollback, restart recovery,
image validation and upload limits, duplicate rejection, weather failures/time selection, provider request
formats, strict critique validation, retry ceilings, partial generation, remix source validation/references,
saved-look snapshots/filtering/deletion, and missing-image fallback.

The real-backend Chromium test uses the production FastAPI routes and SQLite storage with fake external
providers. It verifies registration, upload, generation, critique display, remix, save, page reload, and delete,
with no page errors or external browser requests. Existing mock-server browser regressions also pass.

The first combined run exposed an event-loop conflict between Playwright and async unit tests. Async unit
checks now run in a separate thread/loop; the subsequent combined run passed. This was a test harness issue,
not an external-provider or application failure.

The original critique parser/test suite was imported from `origin/critique-checker` at `a8674d6` and extended.
This record is verification evidence, not a substitute for the course's separate reviewing-agent `REVIEW.md`.

## External verification and limits

- Read the public OpenRouter model/image catalogs; confirmed the configured image and cheap/strong vision
  model slugs and image modalities. No credentials were sent to those public GET endpoints.
- Used current official OpenRouter image and Open-Meteo documentation for request contracts.
- No billed AI inference was run. `eval.py` is provided, but no comparative accuracy or paid latency result is claimed.
- Provider costs are stored when returned, otherwise null. Reconcile against the billing dashboard before updating totals.
- Docker build, deployment, persistent-volume redeploy check, and live end-to-end inference remain unverified.
- Dependency warnings concern Starlette/httpx TestClient and pytest-playwright fixture deprecations; neither failed tests.
