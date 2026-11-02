# Four-question annotation

Each component answers: What is this? Why this choice? What breaks?
What did I learn? Findings (F1–F10) are recorded in CHECKS.md.

## Critique (Nadia)

### What is this?
After an outfit image is generated, a vision model looks at the actual
picture and scores it from 0 to 100 on occasion, aesthetic, styling,
weather, and (if the user uploaded clothes) upload fidelity. It also
lists matches, mismatches, and things it can't tell from a picture. Our
code checks that reply before anything is shown.

### Why this choice?
- **The server computes the overall score itself**, weighted
  30/25/20/15/10 over only the dimensions that were assessed. It never
  trusts the model's own total. Same lesson as my Week 5 receipt lab:
  models produce plausible numbers, not guaranteed ones.
- **The retry rule is plain code:** retry if overall is below 70 or
  there's a major/critical mismatch, at most 2 retries. A model deciding
  its own retries could loop forever and burn money.
- **Two models:** `xiaomi/mimo-v2.6-flash` is cheap and
  `minimax/minimax-m3` is stronger. I tested both on receipts in Week 5.
- **Missing weather means "not assessed", never 0.** A zero would drag
  the score down for something the user can't control.

### What breaks?
- The model wraps its JSON in chatty text. The parser pulls out the
  `{...}`; if there's still no valid JSON, the critique is reported as
  failed, never as passed. This happened live: mimo returned unusable
  JSON for one option, and the app showed it as failed without burning
  an extra attempt.
- A reasoning model can "think" until it runs out of tokens and return
  nothing (m3 on a receipt in Week 5, mimo in class).
- The critic checks garments against the brief, not image defects: it
  never flagged a copied "30% OFF" sticker or multi-panel images.
- Retries cost money, which is why there's a hard cap of 2.

### What did I learn?
- The agent was confidently wrong: in my Week 5 spec it wrote
  `"reasoning": {"effort": "off"}`. `effort` doesn't accept "off", so
  mimo would have returned empty replies. I corrected it to
  `"enabled": false`.
- I built it test-first: 55 tests failed, then passed, before any model
  was connected. The commit history shows the failing tests first.
- A critique can be accurate on small details (a pendant necklace it
  mentioned was really there) and still miss obvious problems.

## Weather (Nadia)

### What is this?
It takes the event's date, time, and location (from the browser, or a
city the user types) and fetches the forecast for that moment from
Open-Meteo. If no forecast exists, it says so instead of guessing.

### Why this choice?
- **Open-Meteo is free and needs no API key:** no secret to leak.
- **Plain code, no AI model:** a language model would invent weather.
- **No manual weather entry:** real data or nothing.
- **Event-local time:** 2 PM in Hartford means 2 PM Eastern, not the
  server's clock.

### What breaks?
- Dates beyond the forecast window (about 16 days) have no forecast, so
  generation continues without weather.
- Misspelled or ambiguous city names aren't found.
- The user can decline location access and type a city instead.
- On Render, the forecast call fails with PROVIDER_ERROR while
  geocoding works, most likely Open-Meteo rate-limiting Render's shared
  IPs. The status code isn't recorded, so it's unconfirmed (F7).
- The UI then says weather is unavailable "for that date", blaming the
  user's date for a provider failure (F10).
- Windows has no time-zone database: 7 weather tests failed on my
  machine until I added `tzdata`.

### What did I learn?
- "No data" is more honest than invented data; missing weather is left
  out of the score rather than penalized.
- Environments differ: tzdata on Windows, then the weather service on
  Render. Tests and live runs catch different things.

## Remix (Nadia)

### What is this?
After seeing three outfits, the user can mix pieces (the blazer from one
option, the top from another) and type changes like "keep the trousers,
swap the jacket." The app generates a new image and gives it a fresh
critique against the revised brief.

### Why this choice?
- **The original brief carries over** (occasion, styling, weather) unless
  the user changes it.
- **Image-conditioned generation:** the chosen source images are sent to
  the image model as visual references. That's why the spec moved to
  Google's image model: the original Flux/Recraft models no longer
  existed on OpenRouter and couldn't use references anyway.
- **The server reuses the original job's location**, so weather stays
  consistent.

### What breaks?
- Kept pieces are only checked against the text list, not compared
  picture to picture: fidelity shows "Not assessed" on remixes, because
  only wardrobe uploads are scored. A subtly changed piece wouldn't be
  caught. The intent said fidelity must be checked, not assumed.
- Conflicting choices, like two jackets from different options.
- Each remix is another image generation, the most expensive call.
- The revisions strip only lasts for the session unless the look is saved.

### What did I learn?
- In the live test it followed "keep A's blazer and trousers, swap in
  C's top, keep B's handbag" correctly.
- Model slugs go stale: half the models in our plan had disappeared from
  OpenRouter, so check them against the live list.
- "Preserve this piece" is a request to the model, not a guarantee.

## Accounts and database (Gabriel; annotated by Nadia and Patrick)

### What is this?
Username and password accounts. Every styling feature needs one, and all
wardrobe items, jobs, and saved looks belong to an account.

### Why this choice?
- Passwords are hashed with Argon2id, never stored in plain text.
- Sessions are a random token in an HttpOnly, SameSite=Lax cookie that
  page code can't read, with a sliding 30-day expiry.
- A wrong username still checks against a dummy hash, so response timing
  can't reveal which usernames exist.
- SQLite: one file, simple, enough for this project. Every query is
  scoped to the signed-in user.

### What breaks?
- SQLite needs a single server process; two would fight over the file.
- On Render's free tier there's no persistent disk, so accounts and
  saved looks are wiped when the service sleeps or redeploys (F9).

### What did I learn?
- The live test confirmed a second account sees none of the first
  account's looks, and data survives a local restart.
- Where data lives matters as much as the code.

## Generator (Gabriel; annotated by Nadia and Patrick)

### What is this?
Turns the brief, weather, and selected uploads into three outfit images
on faceless mannequins, generated in parallel in the background while
the browser polls.

### Why this choice?
- `google/gemini-3.1-flash-image`, because the plan's models no longer
  existed and couldn't take reference images.
- The brief is passed as data, "never instructions", to guard against
  prompt injection.
- Each option gets a different direction (structured, relaxed, layered).
- Retries feed the critique's findings into the next prompt.

### What breaks?
- The model often returns side-by-side panels; validation checks bytes,
  format, and size, not composition (F3).
- Backgrounds can include blurred people; the prompt doesn't forbid it,
  and the team hasn't written a rule yet (F6).
- One of three options sometimes fails, locally and on Render, and the
  reason isn't recorded (F8).
- Image generation is about 90% of the cost (~$0.07 per image).

### What did I learn?
- Check model availability against the live catalog before building.
- A friendly generic error hides causes: our first live failure was an
  HTTP 403 from the key's $20 limit, found only with a probe script (F1).

## Deployment (Gabriel; annotated by Nadia and Patrick)

### What is this?
A Dockerfile and a Render web service. The API key is set in Render's
environment settings, never in the code.

### Why this choice?
- Docker gives the same environment everywhere; Render's free tier
  costs nothing and deploys from GitHub.
- One worker, because jobs and SQLite are process-local.

### What breaks?
- Weather fails on Render (F7), one image sometimes fails (F8), and data
  resets on restart (F9).
- The free service sleeps and takes about a minute to wake, so we demo
  locally.
- Only Gabriel has Render access, so we couldn't read server logs.

### What did I learn?
- Without log access, we diagnosed by reading failure reasons from the
  app's own job data in the browser.
- "Works on my machine" is real: tzdata on Windows, weather on Render.

## Front end (Patrick)

### What is this?
The page users see: brief, wardrobe, three option cards with critiques,
remix, revisions, and saved looks. Plain HTML, CSS, and JavaScript
modules, with no framework and no build step.

### Why this choice?
- Served from the same origin as the API, so the browser only talks to
  our server and the key can never reach it. A Playwright test checks the
  page and every network request for key or provider strings.
- No build step keeps it simple to run and review.
- Built test-first: a mock API and a failing Playwright suite came first,
  then the modules until they passed.

### What breaks?
- No click-to-enlarge on images (F4).
- Wide renders inside a portrait box leave empty bands (F5).
- A sign-out mid-request could briefly show the old account's wardrobe;
  a teammate caught and fixed it.

### What did I learn?
- A friendly error that hides the cause isn't friendly: the provider
  error fix now says when it's a key or credit problem and shows
  "1 of 3" when only some images come back.


## Uploads (Patrick)

### What is this?
Users upload photos of their own clothes (flat lays or hangers, up to
10 MB, PNG/JPEG/WebP/GIF), and generation uses them as references.

### Why this choice?
- A vision preflight rejects photos of people before anything is saved,
  in line with the no-real-people rule.
- Upload fidelity is scored by comparing the upload with the render.

### What breaks?
- The preflight accepted a marketplace screenshot, and its "30% OFF"
  sticker and like/share buttons were copied into the render. The critic
  still gave fidelity 90.

### What did I learn?
- A checker only looks for what you tell it to look for.

## Saved looks (Patrick)

### What is this?
Saves the image, pieces, brief, critique, and the weather it was made
under, so a look can be reopened later.

### Why this choice?
- Weather is labelled as the forecast at generation time, not a fresh
  one, so it doesn't mislead.
- Delete asks for confirmation.

### What breaks?
- On Render's free tier, saved looks vanish when the server restarts (F9).

### What did I learn?
- The live test confirmed it survives a refresh, sign-out, and a local
  restart, and the date filter works.