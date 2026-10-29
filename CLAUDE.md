# FitLab development

- Python 3.11+, FastAPI, SQLite. Serve the existing static frontend from the same origin as `/api/*`.
- Run: `.venv/bin/uvicorn app:app --reload --port 8001`. Offline UI preview: `dev_server:app` on port 8000.
- Install dependencies from `requirements.txt`; install Playwright Chromium for browser tests.
- Verify: `.venv/bin/pytest -q`. Unit/API tests use temporary databases; real-backend browser tests use fake external providers. Never substitute mock data in production services.
- Keep all SQL in `db.py`; scope every user-owned lookup/mutation to the authenticated user. Keep provider calls out of `app.py`.
- API keys stay in the server environment. Never log credentials, provider error bodies, or secret-bearing exceptions. Do not commit databases, uploads, renders, or `.env`.
- Passwords use Argon2id; sessions are opaque cookies with a sliding 30-day expiry. Deployment must enable secure cookies.
- Uploads must show clothing only. Generated images must use fictional mannequins, never real people. Preserve provenance in saved results.
- Image generation is asynchronous, with at most three attempts per option. A failed critique is not a passing score and must not burn additional generation attempts.
- Follow `spec.md` section 7 for critique scoring. See the implementation amendment and `BACKEND.md` for current transport/storage decisions.
- Deploy one worker with persistent database/upload/render storage. See `BACKEND.md` for configuration and outstanding release checks.
- Billed evaluation is explicit: `python eval.py --cases ... --output ...`. Record results and reconcile billed costs; do not claim an evaluation or deployment happened unless verified.
