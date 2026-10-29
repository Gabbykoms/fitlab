# FitLab

**Version 0.1.0**: front-end preview. The web front end is complete and runs against a local stand-in API. The real backend now includes persistent accounts, wardrobe storage, weather, generation jobs, critique/retries, remixing, and saved looks. Offline integration tests pass; live AI quality and deployment are still unverified.

FitLab is an AI outfit studio. You describe an occasion, and FitLab generates three outfit ideas on fictional mannequins. A vision model then critiques each generated image against your brief and the event-day weather. It is a CPSC 415 Team Project 1 (multimodal web app) built by Gabriel, Nadia and Patrick.

## What it does

- **Accounts.** You sign in to keep your wardrobe and saved looks across devices. Every styling feature requires an account.
- **Brief.** You enter the occasion, the aesthetic you want, a styling preference (masculine, feminine or unisex), and the event date and time. Location is optional: either the event city or your browser's location.
- **Event weather.** The server looks up the forecast for the event's time and place. If no forecast is available, outfits are generated and labelled "without weather guidance". FitLab never invents weather.
- **Wardrobe uploads.** You can upload photos of your own clothing, as flat lays or items on hangers. Photos of people are rejected. Selected pieces become visual references, and the critique checks that they were preserved.
- **Three outfit options.** Each option is an image plus a list of its identified clothing pieces.
- **Vision critique.** A vision model reads each actual generated image and scores it 0–100 on occasion, aesthetic, styling, weather, and fidelity to your uploads. It also lists matches, mismatches and uncertainty. A dimension that could not be checked is shown as "Not assessed", never as 0.
- **Automatic retries.** An option that scores below 70, or that has a major or critical mismatch, is regenerated up to 2 more times. Problems that remain after that are disclosed in an "Unresolved" banner. Each card has an attempt log that shows this history.
- **Remix.** You can pick pieces from different options and describe a change (for example, "Keep the trousers, swap the jacket"). FitLab generates a new look and critiques it from scratch. Remixes collect in a revisions strip for the current session.
- **Saved looks.** You can save any look together with its critique and the weather context it was generated under. Saved looks can be filtered by occasion and date, and deleted.

## How it works

```
Browser (static/)  ──same-origin /api/* only──▶  FastAPI server (app.py)
                                                   ├─ db.py         SQLite: users, sessions, wardrobe, jobs, looks
                                                   ├─ weather.py    Open-Meteo forecast for the event time/place
                                                   ├─ generator.py  OpenRouter image model → 3 mannequin outfits
                                                   └─ critique.py   OpenRouter vision model → scored critique + retry rule
```

1. The browser posts the brief to `POST /api/outfits/generate`. The server immediately returns a `job_id`.
2. In the background, the server:
   1. resolves the weather;
   2. generates three images concurrently;
   3. critiques each image against the brief, retrying weak options (at most 3 attempts each).
3. The browser polls `GET /api/outfits/{job_id}` every 2 seconds and renders the options and their critiques.
4. **API keys never reach the browser.** The browser talks only to its own server, and that server makes every model and weather call. `tests/test_browser.py` checks this: it scans the page source for key or provider strings and inspects every network request.

The full design is in [`spec.md`](spec.md), the build plan is in [`plan.md`](plan.md), and the per-feature intent documents are in [`intent/`](intent/).

For backend modules, API routes, implementation order, and verification requirements, see the [backend development guide](BACKEND.md).

## Technologies

| Layer | Technology |
|---|---|
| Front end | Vanilla ES2022 JavaScript (native ES modules, no build step), semantic HTML, and plain CSS with custom properties. Fonts are IBM Plex Sans and IBM Plex Mono, self-hosted under the OFL. |
| Backend | Python 3.11+, FastAPI, Uvicorn, httpx, SQLite |
| AI models (via OpenRouter, server-side only) | `google/gemini-3.1-flash-image` for image generation. `xiaomi/mimo-v2.6-flash` (cheap) and `minimax/minimax-m3` (strong) for vision critique. |
| Weather | Open-Meteo |
| Testing | pytest and Playwright (headless Chromium) |
| Deployment | Render web service (Docker) |

## Getting started

Requires Python 3.11 or newer.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m playwright install chromium   # only needed for the browser tests
```

### Run the front end (available now)

`dev_server.py` is an in-memory stand-in for the API: it needs no keys, makes no network calls, and returns fake images and critiques.

```bash
.venv/bin/uvicorn dev_server:app --reload
# open http://localhost:8000
```

You can trigger edge cases with keywords:

| Keyword | Where | What happens |
|---|---|---|
| `nowhere` | City | Weather is unavailable |
| `unresolved` | Occasion | Option A uses up its retries |
| `nocritique` | Occasion | Option C's critique fails |
| `fail` | Occasion | The whole job fails |
| `person` | Upload label | The upload is rejected |

### Run the tests

```bash
.venv/bin/pytest tests/test_browser.py -q
```

### Run the real backend

```bash
.venv/bin/uvicorn app:app --reload --port 8001
# open http://localhost:8001
```

Set `OPENROUTER_API_KEY` in the server environment for upload preflight and generation. Accounts and stored data need no provider key. Run all offline tests with `.venv/bin/pytest -q`. See [BACKEND.md](BACKEND.md) for storage, model configuration, and deployment requirements.

## Project status

| Item | Status |
|---|---|
| Front end and browser tests | Done (branch `feature/frontend`) |
| Critique engine | Parser reused from `critique-checker`; provider integration and retries implemented |
| Accounts server and database | Implemented on `feature/backend` |
| Weather, generator, styling persistence | Implemented; verified offline with fake providers |
| Live provider evaluation | Pending; no billed inference run during backend implementation |
| Live deployment URL | Not deployed yet |
| Running API cost total | To be recorded from provider usage pages |

## Team

- **Gabriel**: accounts and the generation pipeline
- **Nadia**: weather service and outfit remixing
- **Patrick**: vision critique, uploads, testing and deployment

## Rules this project follows

- No images of real people. Uploads must show clothing only, and generated looks always use fictional mannequins.
- API keys stay in server-side environment variables. A key that appears in any commit is treated as compromised.
