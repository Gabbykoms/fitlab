# FitLab — CHECKS.md

A running ledger of test and evaluation runs. Each entry records the
command actually executed, the commit under test, the full output
(captured verbatim), and what the run proves. Pending work is recorded
honestly as pending: entries only appear once they have been executed.

The budget guidance for the project is $20; the running cost total lives
in `README.md` and is updated from the OpenRouter usage page per the
assignment. Per-attempt cost data is logged by `critique.py` and
`generator.py` and is the source for both ledgers.

---

## Test milestone — critique validator and scorer (commit `46449a2`)

The Test milestone is `tests/test_critique.py`: parsing, schema
validation, weighted overall, and retry trigger — all the work the
Section 7 contract specifies for `critique.py`. No model calls live in
`critique.py`, so the test suite exercises the validator and scorer in
isolation. No API key and no network access are required.

### Red run — commit `a2e9d82` "Failing critique tests"

Command:

```
.venv/Scripts/python.exe -m pytest tests/test_critique.py
```

Output:

```
============================= test session starts =============================
platform win32 -- Python 3.14.1, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\nadia\AppData\Local\Temp\fitlab-red
plugins: anyio-4.15.1
collected 55 items

tests\test_critique.py FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF [ 89%]
FFFFFF                                                                   [100%]

================================== FAILURES ===================================
____________________________ test_parse_clean_json ____________________________

    def test_parse_clean_json():
        raw = json.dumps(CANONICAL)
>       assert parse_reply(raw) == CANONICAL
               ^^^^^^^^^^^^^^^^

tests/test_critique.py:86: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _

raw_text = '{"schema_version": "1.0", "attempt": 1, "model": "xiaomi/mimo-v2.6-flash", "scores": {"occasion": 85, "aesthetic": 78...ible."], "weather_assessed": false, "upload_fidelity_assessed": false, "retry_recommended": false, "retry_reason": ""}'

    def parse_reply(raw_text: str) -> dict:
>       raise NotImplementedError
E       NotImplementedError

critique.py:32: NotImplementedError
______________ test_parse_strips_reasoning_trace_and_code_fence _______________

    def test_parse_strips_reasoning_trace_and_code_fence():
        """Repair (a): drop a leading reasoning trace and a fenced code-block wrapper."""
        body = json.dumps(CANONICAL, indent=2)
        raw = (
            "Let me check each dimension against the rubric.\n"
            "The boots are heavier than a clean relaxed style would suggest.\n"
            "```json\n"
            f"{body}\n"
            "```\n"
        )
>       assert parse_reply(raw) == CANONICAL
               ^^^^^^^^^^^^^^^^

tests/test_critique.py:99: 

(... 53 more NotImplementedError failures, one per test ...)

============================= 55 failed in 0.41s ==============================
```

`a2e9d82` also contains a stub `critique.py` with the public API and
five `NotImplementedError` bodies. The stub exists so the suite collects
and each test fails individually against a known shape of the API
rather than at import time. It is replaced wholesale by `246a4fb`.

### Green run — commit `246a4fb` "Critique validator and scoring"

Command:

```
.venv/Scripts/python.exe -m pytest tests/test_critique.py
```

Output:

```
============================= test session starts =============================
platform win32 -- Python 3.14.1, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\nadia\cpsc415\fitlab
plugins: anyio-4.15.1
collected 55 items

tests\test_critique.py ................................................. [ 89%]
......                                                                   [100%]

============================= 55 passed in 0.06s ==============================
```

### What the 55 tests prove

The tests are organised against the normative source. Every §7.2
constraint, every §7.4 worked example, every §7.7 retry outcome, and
the Section 7.8 "no raw excerpt" rule is covered.

**Parsing — CRT-3.** Six tests. Clean JSON is parsed by `json.loads`.
JSON inside a reasoning trace wrapped in a fenced code block is parsed
by repair (a). JSON inside surrounding prose is parsed by repair (b).
Truncated JSON, non-object JSON, and prose without any JSON each raise
`CritiqueParseError`.

**Schema validation — CRT-4 and Section 7.2.** Twenty-one tests.
Required field absence, wrong type, out-of-range scores, fractional
scores, and boolean scores (which are `int` in Python) are each a
failure. `summary`, `matches`, and `uncertainty` length caps are
checked. The four fields of a mismatch object (`code`, `severity`,
`affected_pieces`, `explanation`) are each required, and unknown
severity or mismatch code values are rejected. `weather_assessed` and
`upload_fidelity_assessed` must match the server-side decision
regardless of what the model returned (CRT-6, CRT-7). The
`retry_recommended` / `retry_reason` coupling is enforced in both
directions.

**Weighted overall — Section 7.4 and CRT-5.** Six tests. The three
worked examples — three assessed dimensions to 84, four assessed to 79,
all five to 80 — are asserted exactly. The denominator is the sum of
the weights of the assessed dimensions only: a `null` weather removes
15 from the denominator, not from the numerator. A `.5` remainder
rounds up. The model's `overall` is tolerated at a difference of 1
from the server's value; a difference of 2 is a failure.

**Retry trigger — Section 7.6, Section 7.7, CRT-11.** Seven tests.
All six worked outcomes from §7.7 are asserted: 92/minor → false, 70/minor
→ false (exactly 70 is not below 70), 69/minor → true, 92/major → true,
64/critical → true with the score branch named first, 88 with no
mismatches and null weather → false. A minor mismatch alone is
verified not to trigger at a high score either.

**End-to-end `finalize_reply` — Section 7.6 and Section 7.8.** Nine
tests. A valid document produces `status: "ok"`. An unparseable
response and a schema violation each produce
`status: "failed", error: "invalid_response"`. The server's `overall`
overwrites the model's. A false `retry_recommended` the server
disagrees with is overridden to true; a true one without a qualifying
trigger is overridden to false. The raw model text is never returned.

### How to reproduce

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install httpx pytest
.venv/Scripts/python.exe -m pytest tests/test_critique.py
```

Requires no API key. No network requests are made.

---

## Front-end milestone — Playwright browser check (`feature/frontend`)

The browser check is `tests/test_browser.py`: 20 Playwright tests that
drive headless Chromium through the front end. The file lives on branch
`feature/frontend`, and the run below is against commit `6eae562`
("docs: README overview and FE-12 polling pause/resume"), the tip of
that branch at the time of the run.

The suite starts `dev_server.py` itself — an in-memory stand-in for the
`spec.md` §3.1 API — on a free port, waits for `/api/health`, and points
Chromium at it. `dev_server.py` holds no keys and makes no network
calls, so the suite needs no `OPENROUTER_API_KEY` and no network access.

### Green run — commit `6eae562` on `feature/frontend`

Command (run with the project's `.venv`, from a scratch checkout of
`feature/frontend`; the `rootdir` line below is that scratch path, and
the checkout was deleted after the run):

```
.venv/Scripts/python.exe -m pytest tests/test_browser.py
```

Output:

```
============================= test session starts =============================
platform win32 -- Python 3.14.1, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\nadia\.fitlab-browser-run
plugins: anyio-4.15.1, playwright-0.10.0
collected 20 items

tests\test_browser.py ....................                               [100%]

======================== 20 passed in 61.93s (0:01:01) ========================
```

An earlier run of the same suite against the same commit on the same
machine reported `20 passed in 52.60s`. Both runs collected and passed
the same 20 tests.

Cost of this run: $0. No model was called.

### What the 20 tests prove

**Key isolation — spec.md §5 SEC-2. Three tests.** Every file under
`static/` (`.html`, `.js`, `.css`) is scanned for provider and key
strings — `openrouter`, `OPENROUTER_API_KEY`, `api_key`, `Bearer`,
`google/gemini`, `xiaomi/`, `minimax/`, `openai/`, `anthropic/` — and
none of them is present. The same strings are checked in the three
assets the server actually serves (`/`, `/app.js`, `/style.css`). A
third test records every request the page makes during a full
sign-up → upload → generate flow and asserts that each one is
same-origin (or a local `data:` / `blob:` preview) and that no
`/api/*` request carries an `Authorization` header.

**Authentication — two tests.** A signed-out visitor sees the auth
dialog, the wardrobe and results panels stay hidden, and the server
answers `GET /api/wardrobe` with 401. A wrong password shows the plain
sentence "That username and password do not match." and does not leak a
status code.

**Brief and wardrobe — four tests.** Generate stays disabled until the
brief is complete, and is disabled again once the event date is in the
past; the location line names the city that was typed; the upload rule
is shown and a photo labelled "person" is rejected with a message saying
so, leaving no wardrobe item; a selected piece is echoed in the brief.

**Results and critique display — five tests.** Three option cards render
with an overall score, an attempt log and a piece list; an unassessed
dimension reads "Not assessed" and never "0%", and the weather readout
says "without weather guidance" when the city is `nowhere`; an option
that used up its retries shows the unresolved banner and three
attempt-log entries; a failed critique is disclosed in words and shows
no score; a failed job shows a sentence, not a status code or a JSON
body.

**Remix, saved looks, layout — four tests.** Remix stays disabled until
pieces from two different options are chosen, then adds a revision card;
a saved look can be filtered by occasion and deleted; the page has no
horizontal overflow at 360 px.

**Regressions from the code review — three tests.** Generate stays
disabled while a job is running; signing out mid-job leaves no stale
results and no "NaN"; revisions keep their saved state and survive a
new generate.

### What this run does not prove

The suite runs against `dev_server.py`, a stand-in that returns fake
images and fake critiques and makes no model calls. It exercises the
whole front end without the real server, and it proves the browser code
does not reach for a key or a provider endpoint. It does not exercise
the real backend: `app.py`, `db.py`, `weather.py`, `generator.py` and
`critique.py` are never started, no OpenRouter call is made, no SQLite
row is written and no weather lookup happens. The key-isolation
assertions are therefore assertions about the browser code and the shape
of the stub API; the same check has to be re-run against `app.py` once
it lands — with a real `OPENROUTER_API_KEY` in the server environment —
to show that the key stays off the browser side of the real server too.

One requested test is still missing. FE-12 says polling pauses while
the page is hidden for more than 60 seconds and resumes when the page
is visible again. The behaviour is implemented in `static/js/jobs.js`
(`HIDDEN_LIMIT_MS`), and a separate review pass over the front end
(`REVIEW.md`, produced by another agent and not committed) found no
blocking issues and asked for a test covering the pause and the resume.
No test covers it yet, so the suite does not check it.

### How to reproduce

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m playwright install chromium
.venv/Scripts/python.exe -m pytest tests/test_browser.py
```

Check out `feature/frontend` first. Requires no API key and no network
access.

---

## Backend

### 2026-10-29 — remaining backend implementation

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

### External verification and limits

- Read the public OpenRouter model/image catalogs; confirmed the configured image and cheap/strong vision
  model slugs and image modalities. No credentials were sent to those public GET endpoints.
- Used current official OpenRouter image and Open-Meteo documentation for request contracts.
- No billed AI inference was run. `eval.py` is provided, but no comparative accuracy or paid latency result is claimed.
- Provider costs are stored when returned, otherwise null. Reconcile against the billing dashboard before updating totals.
- Docker build, deployment, persistent-volume redeploy check, and live end-to-end inference remain unverified.
- Dependency warnings concern Starlette/httpx TestClient and pytest-playwright fixture deprecations; neither failed tests.

---

## Live smoke test — 2026-10-31 (commit `6c6e166`)

The first run of the **real** application against **real** providers: `app.py`
served by Uvicorn on port 8001, a live OpenRouter key in the server
environment, live Open-Meteo weather, and live image and vision calls to
OpenRouter. Commit `6c6e166` is the tip of `critique-checker` at the time of
the run; the working tree was clean.

This is the first time billed inference has been run against the project. The
entries above are all offline verification with fake providers; this one is not.

### Setup

```
.venv/Scripts/python.exe -m uvicorn app:app --port 8001
```

The key was supplied through the server environment, not through a `.env`
file — the app does not load those. The server ran from the repository root
against the project's own SQLite database and private render directory, so the
persistence checks below exercise the same storage the deployment will use.
No mock data was substituted for any provider.

### The brief

| Field | Value |
|---|---|
| Occasion | Conference |
| Aesthetic | Smart, business, simple |
| Styling preference | Feminine |
| City | Hartford |
| Event date and time | 2026-11-05 14:00 |
| Notes | "Avoid bright colours. Keep neutral and minimal." |

No wardrobe items were uploaded, so `upload_fidelity` was `null` for every
critique in this run.

### The first attempt failed, and the error hid the cause

The first submission failed about six seconds after it was accepted. The job
row recorded the generic message "The outfits could not be generated. Please
try again." and no options at all.

A separate probe script against OpenRouter established the real cause: the
server was answering **HTTP 403**, because the account had reached its
**$20 credit limit**. Nothing in the app's own output said this.

That gap is a finding in its own right, and it is recorded as **F1** below.
The limit was raised and the brief was re-submitted; the second attempt
completed.

### The completed run

The generate job was created at `22:43:45.923Z` and updated at
`22:44:18.239Z` — **32.3 seconds** wall clock for all three options
(18:43:45 → 18:44:18 local, UTC−4).

**Weather.** Resolved to Hartford, Connecticut, United States
(41.76371, −72.68509) in the `America/New_York` zone, with the event instant
read as `2026-11-05T14:00` — the brief's local time, not UTC. 64.8 °F
(feels like 66.7), **overcast** (weather code 3), 28% chance of precipitation,
0.0 mm, wind 4.4 mph. The critique of every option therefore had a weather
dimension assessed rather than "Not assessed".

**Generation.** All three images came from `google/gemini-3.1-flash-image`,
each 1408×768 (1.83:1), each generated concurrently.

**Critiques.** All three were requested from `xiaomi/mimo-v2.6-flash`.

| Option | Attempt | Overall | occasion / aesthetic / styling / weather | Outcome |
|---|---|---|---|---|
| A | 1 | **86** | 90 / 85 / 80 / 85 | One minor mismatch (`STYLING_PREFERENCE_MISMATCH`, on the suit jacket and turtleneck) |
| B | 1 | **83** | 82 / 84 / 85 / 78 | No mismatches |
| C | 1 | — | — | **Critique failed** (`invalid_response`) — no score, disclosed in words |

Every option finished on `attempts: 1`, with `retry_exhausted: false` and an
empty `unresolved` list. **Option C's failed critique consumed no further
generation attempt**, which is the behaviour the retry-ceiling rule requires:
a failed critique is not a passing score and must not burn an attempt. The
provider tokens for that failed call were still billed and are recorded
(`$0.000240689`).

**The critique was checked against the pixels.** Option A's critique says
"Feminine styling is only lightly suggested through the pendant, belt, and
tote". The full-size render for option A shows a gold chain with a round
pendant, a black belt and a black tote. The claim is correct.

### Remix

The remix job ran from `22:54:26.783Z` to `22:54:56.743Z` — **30.0 seconds**
(18:54:26 → 18:54:56 local).

The revision instruction was "Keep option A's blazer and trouser but swap
shirts with option c", and the preserve list the server received was four
text pieces: A's **Blazer** (dark grey), A's **Trousers** (dark grey), B's
**handbag** (green), and C's **Beige Underlayer**.

The remix scored **85** (occasion 88, aesthetic 85, styling 84, weather 80),
with one minor mismatch: the underlayer "appears to have a high neckline with
layered detailing rather than a simple shirt". The render supports that —
the swapped-in top is cream with a layered beaded neckline rather than the
plain beige layer of option C. The blazer and trousers came through in dark
grey, and the tote came through dark green.

### Persistence and access control

| Check | Result |
|---|---|
| Saved look survives a page refresh | Pass — occasion `Conference`, event date `2026-11-05`, overall 86 |
| Saved look survives sign-out | Pass |
| Saved look survives a server restart | Pass — the row and the render file are both on disk |
| A second account sees no looks | Pass — the second account was created at `23:45:11Z`; the `looks` table holds exactly one row, owned by the first account |
| Date filter | Pass — the drawer filters on `from_date` / `to_date` against the event date |
| Delete asks to confirm | Pass — the drawer swaps the delete control for **Confirm delete** / **Cancel** (`static/js/saved.js:59`) |

### Cost

Provider-reported cost for this run:

| Part | Cost |
|---|---|
| 3 image generations (generate job) | $0.202095 |
| 1 image generation (remix job) | $0.069149 |
| 5 piece-extraction calls | $0.000772938 |
| 4 critique calls (one of which failed) | $0.000886693 |
| **Total for this run** | **$0.272904** |

The failed first attempt produced no options and recorded no provider cost —
the request was rejected with 403 before any billable generation.

This figure is the run's own reported cost. The project's running total must
still be reconciled against the OpenRouter usage page, and the credit limit
that stopped the first attempt means the account had already reached that
ceiling before this run.

### Findings

**F1 — A provider failure is reported as a generic sentence, and the server
output does not say why.** The 403 surfaced to the user as "The outfits could
not be generated. Please try again.", with nothing in the server log to
distinguish a spent credit balance from a transient fault. It took a separate
probe script to find the cause. The gap is in `provider.py`: only 429 is
handled by status (`provider.py:31`); every other non-2xx goes through
`response.raise_for_status()` into the single catch-all at `provider.py:38`,
which produces one generic sentence for every other failure. The status code
is not logged, and the provider body must never be logged (CLAUDE.md), so
nothing survives to tell an operator what happened. There is also a
**divergence from the spec**: the generation failure-handling table in
`spec.md` says HTTP 401/403 should fail the job with "the styling service is
not configured right now", but the code never produces that sentence. The
spec row and the implementation disagree, and one of them has to change.

**F2 — Remix fidelity is asserted against the text list, not against the
images.** The preserve list is a set of names, categories and colours, and the
critique is asked to check the generated image against that text. In this run
the pixels happened to agree with the text, but nothing compares the remix
against the *source option images*: `BACKEND.md` records that source outfit
images only "guide generation", and a remix's `upload_fidelity` is `null`,
because only real wardrobe uploads are scored for fidelity. The same run
produced a concrete divergence between the text layer and the pixels — the
piece-extraction call described the remix's handbag as a "leather tote bag"
in **black**, while the render clearly shows a **dark green** tote and the
preserve list said green. The text list is therefore not a reliable stand-in
for the pixels, which is the argument for checking the images themselves.

**F3 — Option B came back as a two-panel composite.** The render for option B
is a single 1408×768 file containing two near-identical side-by-side panels
of the same outfit with a visible seam down the middle. It passed validation
unchanged: `media.inspect_image` (`media.py:16`) checks that the bytes
decode, the format is supported and the size is within bounds, and there is no
aspect-ratio or composition check anywhere in the pipeline. The critique
scored the pair as a single look and gave it 83.

**F4 — There is no click-to-enlarge on generated images.** Nothing in
`static/` opens an image larger: the only dialogs are the auth dialog and the
saved-look drawer, and there is no lightbox or zoom handler. The card figure
is `aspect-ratio: 3 / 4` with `object-fit: contain`
(`static/css/components.css:61`), so the full-size render is never
inspectable in the app. This is also why checking the pendant claim against
the full-size image had to be done outside the browser.

**F5 — Empty space above the image in the result card.** The image model
returns landscape 1408×768 (1.83:1), but `.card-figure` reserves a portrait
3:4 box and contains the image, so the photo is letterboxed with empty bands
above and below it. Below 760 px the rule becomes `aspect-ratio: auto;
height: min(70vw, 380px)` (`static/css/layout.css:122`), which letterboxes
the same way. The rendered mannequins also carry generous headroom of their
own, which compounds it.

**F6 — Backgrounds show occasion context, and option B's background contains
people.** Options A and C and the remix have blurred architectural or studio
backgrounds with no people in them. Option B's two-panel image has blurred
conference attendees in business attire; the figures are blurred beyond
recognition at full size and no face is identifiable, so this is not a
breach of the "no real person" rule as written. But that rule as written
constrains only the mannequin: the prompt in `spec.md` says the mannequin has
"no face, skin, hands, or identifiable features", and GEN-3 says "Every
generated image depicts a fictional mannequin with no face, skin, hands, or
identifiable features". Neither says the background must be free of people,
and the README's claim that generated looks never depict real people is not
guaranteed by the current prompt. **The team has to decide this and record
it in `spec.md`** — whether backgrounds may contain people at all, and if so
what the rule is (blurred only, no identifiable faces, no foreground people).
No code change should follow until that decision is written down.

### What this run proves

- The real server, against the real providers, produces three images and
  critiques them from their actual pixels, end to end, in 32 seconds.
- Weather resolution, the event-local time zone, the full brief, the
  generated piece lists and the critique all agree with each other and with
  the stored renders.
- The retry ceiling behaves correctly under a live failure: a failed critique
  was disclosed with no score and burned no extra generation attempt.
- Saved looks persist across a refresh, a sign-out and a server restart;
  a second account sees none of them; the date filter and the delete
  confirmation work.
- Billed inference works end to end, and the provider-reported cost for one
  full brief plus remix is **$0.27**.

### What this run does not prove

- **One brief, one occasion, one date, one city, one account pair.** Nothing
  here suggests the app behaves the same for uploads, for a different
  climate, or for a second user generating their own looks.
- **No upload fidelity.** No wardrobe item was ever uploaded (`wardrobe_items`
  is empty), so `upload_fidelity` was `null` on every critique and the
  preflight upload path was never exercised live.
- **No live retry.** No option fell below 70 and no major or critical
  mismatch was raised, so the live retry ceiling — up to three attempts per
  option — was never reached. Only the *failed-critique* path was exercised.
- **No model comparison.** The strong critique model was not called; it has
  still not been run against the cheap one. `eval.py` remains pending.
- **No deployment.** This was a local Uvicorn process. The Docker build, the
  persistent-volume redeploy, and the secure-cookie behaviour behind HTTPS
  are all still unverified.
- **No quality judgement** beyond the checks listed above. The images are
  provider output; a human has not yet rated whether they are good outfits.
- **No reconciled total.** $0.27 is this run's reported cost, not the
  project's running total.

### How to reproduce

```
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m uvicorn app:app --port 8001
```

Set the provider key in the server environment before starting Uvicorn (the
app does not read `.env` files). The run requires network access and consumes
roughly $0.27 per full brief plus remix; if the account has no credit
available, the job fails with the generic error described in F1.

---

## Pending — not yet runnable

The eval entry is recorded here so this ledger is honest about what has
not been verified. It is filled in when the underlying component exists.

### Pending — vision critique evaluation (`eval.py`)

`eval.py` is the one billed script in the project (spec.md Section 6,
"Testing strategy"). It runs the same set of generated outfits through
both the cheap critique model (`xiaomi/mimo-v2.6-flash`) and the
strong critique model (`minimax/minimax-m3`), and records per-model
agreement, mismatch-detection agreement, retry-trigger agreement,
latency, and cost into this file.

**Status: pending.** The evaluation requires generated outfit images
to critique. Images now exist — the live smoke test above produced
three outfits and a remix — but none of them exercises the two
dimensions the cheap-vs-strong comparison is meant to evaluate: the
live run had no wardrobe uploads, so `upload_fidelity` was `null`
throughout, and no option crossed the retry threshold, so the retry
loop never ran. The browser check does not help either: it drives the
front end against the fake outfits in `dev_server.py`, and the eval
needs real generated images. The entry will appear here once a set of
cases with uploads and a retry-triggering brief has been generated and
passed to `eval.py` as a case file.
