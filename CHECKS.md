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
rootdir: C:\Users\nadia\cpsc415\.fitlab-browser-run
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
to critique. None have been produced yet — `generator.py` is not
implemented. Running `eval.py` against critique-only output would not
exercise the upload-fidelity dimension or the retry loop, which are
the parts the cheap-vs-strong comparison is meant to evaluate. The
browser check above does not change this: it drives the front end
against the fake outfits in `dev_server.py`, and the eval needs real
generated images. The entry will appear here once at least one generated
outfit has been produced through the end-to-end generate → critique →
retry pipeline.
