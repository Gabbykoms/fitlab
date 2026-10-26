# Plan

## Deployment Target
- **Platform:** Render Web Service (Docker / Python 3.11 environment).
- **Architecture:** FastAPI application serving static frontend assets (`HTML/CSS/JS`) and exposing `/api/*` endpoints. Data persistence backed by SQLite (`fitlab.db`).
- **Secrets Management:** `OPENROUTER_API_KEY` and optional `WEATHER_API_KEY` stored strictly as server-side environment variables in Render; never bundled in frontend assets or exposed to the client browser.

## Files to create or change
| File | Purpose |
|---|---|
| `spec.md` | Formal architecture specification covering all 7 intent areas, component interfaces, language and model justifications, failure modes, and cost estimates. |
| `app.py` | FastAPI application server providing REST endpoints (`/api/auth/*`, `/api/wardrobe/*`, `/api/outfits/*`, `/api/critique/*`, `/api/looks/*`) and serving static assets while keeping API keys isolated. |
| `db.py` | SQLite database schema and helper functions for user accounts, hashed credentials, uploaded wardrobe metadata, generated outfits, and saved looks. |
| `weather.py` | Event weather service integrating with Open-Meteo API using event date, time, and coordinates/city, with graceful fallback when forecasts are out of range. |
| `generator.py` | Image generation pipeline using OpenRouter image models to create three distinct mannequin outfits per brief and incorporate upload references. Model: `google/gemini-3.1-flash-image` (Nano Banana 2) as the default — it accepts image input and produces image output, which is required for the upload-fidelity feature. Benchmark alternative: `google/gemini-3-pro-image` (Nano Banana Pro). *Amended 2026-10-25: `black-forest-labs/flux-1-schnell` and `recraft/recraft-v3` were removed from the OpenRouter catalog and are unreachable; neither could do image-conditioned generation anyway.* |
| `critique.py` | Multimodal vision critique service using OpenRouter vision models to inspect generated images, check brief compliance & uploaded clothing fidelity, produce scores with explanations, and trigger auto-retries (max 2). Models: `xiaomi/mimo-v2.6-flash` (cheap) and `minimax/minimax-m3` (strong); both accept image input. Every MiMo call must send `reasoning: {"enabled": false}`, otherwise the reasoning trace precedes the JSON and the response will not parse. The critique JSON contract in `spec.md` §7 is normative for `tests/test_critique.py`. *Amended 2026-10-25: `openai/gpt-4o-mini` and `minimax/minimax-01` were the originally named models; `openai/gpt-4o-mini` is retained as an eval comparison point only.* |
| `static/index.html` | Single-page application structure: navigation, account auth dialog, wardrobe upload tray, occasion & weather prompt panel, 3-option outfit showcase, remix editor, and saved looks drawer. |
| `static/app.js` | Frontend controller managing DOM updates, image uploads, remix piece selection, polling/rendering generation results, and error notifications without holding API credentials. |
| `static/style.css` | Responsive styling, grid layout for the 3 outfit cards, critique breakdown badges, score indicators, and upload preview containers. *Amended 2026-10-26: now an entry point that `@import`s `static/css/{tokens,base,layout,components}.css`.* |
| `static/js/*.js` | *Added 2026-10-26.* Native ES modules that `static/app.js` imports, with no build step: `api`, `state`, `dom`, `toast`, `auth`, `wardrobe`, `brief`, `jobs`, `scores`, `results`, `remix`, `saved`. Keeps every file under 400 lines. |
| `static/css/*.css` | *Added 2026-10-26.* Design tokens (light lab-notebook theme, teal accent), base and typography, the split-workbench layout, and components. See `spec.md` §3.6 "Visual design". |
| `static/fonts/` | *Added 2026-10-26.* Self-hosted IBM Plex Sans and IBM Plex Mono woff2 files plus their OFL license. Self-hosted because SEC-2 forbids CDN requests. |
| `dev_server.py` | *Added 2026-10-26.* A dev-only in-memory stub of the `spec.md` §3.1 API. It returns fake images and critiques shaped like §7 and has keyword-triggered edge cases. Used to build the front end before `app.py` exists, and as the stub provider for `tests/test_browser.py`. Holds no keys and makes no network calls. |
| `requirements.txt` | *Added 2026-10-26.* `fastapi`, `uvicorn`, `python-multipart`, `pytest`, `pytest-playwright`. |
| `tests/test_weather.py` | Unit tests for weather resolution: coordinates lookup, city override, out-of-range forecast handling, and missing-weather fallback (requires no API key). |
| `tests/test_db.py` | Unit tests for the data layer: ownership isolation (user A cannot read user B's rows), password hashing, session expiry, idempotent schema creation, duplicate-username handling, and the saved-look round trip (requires no API key). |
| `tests/test_critique.py` | Unit tests for critique payload parser, rubric scoring calculation, mismatch detection, retry triggers, and uncertainty disclosure (requires no API key). |
| `tests/test_browser.py` | Playwright browser automation test verifying client-server key isolation, UI element rendering, generation trigger, and network request inspection. |
| `eval.py` | Vision critique evaluation harness testing prompt compliance, clothing fidelity preservation, and retry threshold accuracy against baseline outfit images. Benchmark pair: `xiaomi/mimo-v2.6-flash` (cheap) against `minimax/minimax-m3` (strong), with `openai/gpt-4o-mini` retained as a third comparison point. |
| `CHECKS.md` | Log of test execution (unit tests, Playwright browser run, eval results with both cheaper and frontier vision models, and cost tracking). |
| `CLAUDE.md` | Project conventions, local run/test commands, safety rules (no photos of real people), and deployment procedures. |
| `README.md` | Project overview, team members, setup instructions, architecture summary, live deployment URL, and running cost total. |

## Questions addressed during plan review
- **"How does the app guarantee that API keys never leak to the client?"**
  - Following the course's `key-on-server` architecture pattern, the browser only communicates with our FastAPI backend on `/api/*`. The client script (`static/app.js`) contains no references to OpenRouter, API keys, or provider endpoints. The backend pulls `OPENROUTER_API_KEY` from the environment, attaches authentication headers server-side, executes generation and critique calls, and returns only clean JSON and image URLs/base64 to the client. This is verified in `tests/test_browser.py` by inspecting network requests to ensure no `Authorization` header leaves the browser and no external AI endpoints are called directly.
- **"How does the visual critique ensure the model evaluates the actual image and not just the prompt?"**
  - The critique engine (`critique.py`) encodes the newly generated PNG/JPEG into a base64 data URI (`data:image/png;base64,...`) and sends it directly in the OpenRouter multimodal request payload (`messages[].content` containing both `image_url` and text prompt). The system prompt instructs the vision model to extract visible garments, silhouettes, colors, and textures from the pixel data and score them against the brief. For wardrobe uploads, both the original reference photo and the generated look are supplied to the vision model to check visual fidelity and preservation.
- **"What happens when an uploaded item conflicts with the requested weather or occasion?"**
  - Rather than silently replacing the item or failing silently, `generator.py` attempts to style around the piece with appropriate complementary layering (e.g., adding an overcoat or umbrella for cold/rain), while `critique.py` detects the tension and articulates the conflict in plain language (e.g., "The selected linen shorts provide low insulation for a 45°F evening; a heavier outer layer was paired to compensate"). If weather data is unavailable, weather appropriateness is explicitly omitted from scoring rather than hallucinating conditions.
- **"What could break in step 5 (auto-retry generation), and how do we prevent runaway API costs or infinite loops?"**
  - A vision critique might continually flag minor aesthetic discrepancies, triggering repeated generation calls and draining API credits. We address this by: (1) enforcing a strict hard limit of at most two automatic retries per option (maximum 3 generation attempts total); (2) requiring a threshold score below 70% or an explicit mismatch flag before triggering a retry; (3) logging token usage and cost per attempt; and (4) if mismatches persist after 2 retries, halting generation and presenting the best option alongside an honest disclosure of unresolved issues.
- **"How do we enforce the course policy prohibiting images of real people?"**
  - The UI and upload specifications explicitly restrict uploads to clothing-only photos (flat-lays or hangers). On upload, a lightweight vision pre-flight filter verifies no human faces or bodies are present before saving to the wardrobe. Generated looks explicitly specify "displayed on a neutral, fictional mannequin with no human facial features or identity" in their generation prompts.

## Front-end decisions (answered by Patrick, 2026-10-26)
- **Theme:** light lab notebook (paper and grid background, ink text) with a lab-teal accent. The lab metaphor stays subtle and lives in the visuals; labels use plain words.
- **Layout:** split workbench, with a controls column on the left, results and remix on the right, and saved looks in a drawer.
- **Scores:** a mono overall readout plus a bar gauge for each dimension, with a tick at the 70 retry threshold. Unassessed dimensions are drawn as hatched "Not assessed" bars.
- **Attempt log:** collapsible, one row per entry in `critique_history`.
- **Critique model:** server default only, with no UI toggle.
- **Remix revisions:** a session-only revisions strip.
- **Saved looks:** view and delete, with no rename.
- **Motion:** subtle scan shimmer while jobs run, respecting reduced motion.
- **Build approach:** the front end is built on branch `feature/frontend` against `dev_server.py` until `app.py` lands.
- **Front-end testing:** Playwright through pytest only (`tests/test_browser.py`).

## Order of work
1. **Core Scaffolding & Specifications (`spec.md`, `CLAUDE.md`, `db.py`, `app.py`):**
   - Author formal `spec.md` synthesizing the 7 approved intent documents.
   - Establish `CLAUDE.md` with development commands and safety guidelines.
   - Implement SQLite database schema (`db.py`) for users, sessions, wardrobe items, generated looks, and critique records.
   - Set up basic FastAPI application skeleton (`app.py`) with session-based authentication routes (`/api/auth/register`, `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`).
2. **Weather Integration (`weather.py`, `tests/test_weather.py`):**
   - Implement Open-Meteo client to fetch forecast data using latitude/longitude or city geocoding for the specified event date/time.
   - Handle date boundaries: return standard forecast for dates within range, or graceful fallback response (`weather_available: false`) for out-of-range dates or network errors.
   - Write unit tests in `tests/test_weather.py` checking successful lookup, location override, and fallback handling without requiring an API key.
3. **Wardrobe Upload & Storage (`app.py`, `static/`):**
   - Add image upload endpoints (`POST /api/wardrobe/upload`) with clothing-only verification and local/cloud storage.
   - Build client upload tray in `static/index.html` allowing users to preview flat-lays, tag garments (e.g., top, bottom, outerwear), and select pieces for styling.
4. **Outfit Generation Service (`generator.py`):**
   - Implement prompt builder combining event occasion, aesthetic mood, styling preferences, event weather summary, and uploaded piece descriptions.
   - Connect to OpenRouter image generation API to generate three distinct outfit options on fictional mannequins.
   - Return outfit metadata identifying visible individual clothing items.
5. **Multimodal Vision Critique & Auto-Retry Loop (`critique.py`, `tests/test_critique.py`):**
   - Implement vision critique pipeline passing generated image base64, uploaded reference images, and brief parameters to OpenRouter vision model.
   - Enforce structured JSON critique output: scores across occasion, aesthetic, styling, weather (if available), and upload fidelity, plus summary text and retry recommendations.
   - Implement the auto-retry controller (max 2 retries per look) when scores fall below threshold or mismatches are flagged.
   - Write unit tests in `tests/test_critique.py` validating schema parsing, rubric weighting, and retry ceiling logic.
6. **Outfit Remixing & Refinement (`generator.py`, `app.py`, `static/app.js`):**
   - Implement remix endpoint (`POST /api/outfits/remix`) allowing users to combine pieces across generated options and provide natural language revision instructions ("Keep trousers, swap jacket").
   - Generate updated mannequin look and execute fresh vision critique against the revised brief.
7. **Saved Looks & User Gallery (`app.py`, `db.py`, `static/`):**
   - Implement endpoints to save complete look payloads (image, pieces, generation brief, critique scores, unresolved issues).
   - Display saved looks in a user wardrobe drawer with filterable dates and occasions.
8. **Automated Testing, Browser Verification, & Eval (`tests/test_browser.py`, `eval.py`, `CHECKS.md`):**
   - Write and run Playwright browser test in `tests/test_browser.py` asserting no client-side key leakage, proper DOM transitions, and authenticated access enforcement.
   - Build `eval.py` running benchmark briefs across cheap vs. frontier vision models, recording comparative latency, cost, and critique accuracy in `CHECKS.md`.
9. **Deployment & Documentation (`README.md`, Render setup):**
   - Create Dockerfile / `requirements.txt` for Render deployment.
   - Deploy to Render web service, configure environment secrets, and verify live URL.
   - Complete `README.md` with architecture details, setup commands, and cumulative cost ledger.

## Risks
- **Vision model latency and cost runaway:** Multiple retries across 3 outfit options could take 30+ seconds and drain credit. *Mitigation:* Strict 2-retry ceiling; parallel generation calls; use fast, cost-effective vision models (`xiaomi/mimo-v2.6-flash` for the default critique, `minimax/minimax-m3` for the stronger comparison) for critique.
- **Image fidelity with uploaded garments:** Diffusion models may alter patterns or colors of uploaded clothing. *Mitigation:* Multimodal critique explicitly compares generated output with upload references and reports discrepancies; UI makes clear that fidelity is targeted rather than guaranteeing identical reproduction.
- **Forecast unavailability for distant events:** Events weeks away cannot get hourly forecasts. *Mitigation:* Weather service explicitly flags unavailable forecast; prompt generator and critique rubric omit weather factors cleanly rather than fabricating conditions.
- **Accidental API key leakage:** Web client could inadvertently call external endpoints. *Mitigation:* Server-only proxy architecture; Playwright assertions check that all outbound browser network requests target `/api/*` and carry no external authorization headers.
- **Policy violation regarding images of people:** Users might upload portraits. *Mitigation:* Explicit client-side guidance and pre-flight validation requiring clothing-only images; generation prompt enforces fictional mannequin representation.

## Proof
- **Unit Tests (No Key Required):** Run `pytest tests/test_weather.py tests/test_critique.py`. All tests pass: validates weather fallback logic, date parsing, critique JSON schema validation, scoring calculations, and retry limit bounds.
- **Browser-Driven Test (Key Isolated on Server):** Run `pytest tests/test_browser.py`. Playwright runs headless Chromium, navigates through login, wardrobe upload, brief submission, verifies that no request to `openrouter.ai` leaves the browser, and asserts that no `Authorization` headers or secret tokens appear in client DOM or network traces.
- **Vision Critique Evaluation (Billed Call):** Run `python3 eval.py`. Evaluates sample generated looks against target briefs using both a cheap model (`xiaomi/mimo-v2.6-flash`) and a stronger model (`minimax/minimax-m3`), with `anthropic/claude-sonnet-5.5` as an additional escalation point and `openai/gpt-4o-mini` retained as a third comparison, outputting comparative scores, mismatch detections, and cost per run into `CHECKS.md`.
- **Live Deployment Proof:** HTTP `GET https://<render-url>/api/health` returns status code 200 with database connectivity and secret verification confirmed.

## Subagents and parallel work
- **Gabriel (Accounts & Generation Pipeline):** Lead on `db.py`, authentication routes in `app.py`, and `generator.py` (intents: `accounts.md`, `outfit-generation.md`).
- **Nadia (Weather Service & Outfit Remixing):** Lead on `weather.py`, `tests/test_weather.py`, and remix controller in `app.py` (intents: `event-weather.md`, `outfit-remixing.md`).
- **Patrick (Vision Critique Engine, Uploads, & Testing/Deployment):** Lead on `critique.py`, `tests/test_critique.py`, `tests/test_browser.py`, `eval.py`, and Render deployment (intents: `clothing-uploads.md`, `saved-looks.md`, `visual-critique.md`).
- Parallel branches / worktrees will be used for independent feature modules (`feature/weather`, `feature/generation`, `feature/critique`), merging via reviewed pull requests into `main` with passing test suites.

**Approved by:** Gabriel, Nadia, Patrick, October 19, 2026
