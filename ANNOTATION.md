\# Four-question annotation



\## Critique (Nadia)



\### What is this?

After an outfit image is generated, a vision model looks at the actual picture and scores it from 0 to 100 on occasion, aesthetic, styling, weather, and (if the user uploaded clothes) upload fidelity. It also lists matches, mismatches, and things it can't tell from a picture. Our code then checks that reply before anything is shown.



\### Why this choice?

\- \*\*The server computes the overall score itself\*\*, weighted 30/25/20/15/10 over only the dimensions that were actually assessed. It never trusts the model's own total. Same lesson as my Week 5 receipt lab: models produce plausible numbers, not guaranteed ones.

\- \*\*The retry rule is plain code:\*\* retry if overall is below 70 or there's a major/critical mismatch, at most 2 retries. A model deciding its own retries could loop forever and burn money.

\- \*\*Two models:\*\* `xiaomi/mimo-v2.6-flash` is cheap, and `minimax/minimax-m3` is stronger. I tested both on receipts in Week 5, so the choice is based on real runs, not guesses.

\- \*\*Missing weather means "not assessed", never 0.\*\* A zero would unfairly drag the score down for something the user can't control.



\### What breaks?

\- The model wraps its JSON in chatty text. The parser pulls out the `{...}`, and if there's still no valid JSON, it reports the critique as failed rather than pretending it passed.

\- A reasoning model "thinks" until it runs out of tokens and returns nothing. m3 did exactly this on my Target receipt in Week 5, and mimo did it in class.

\- Scores are opinions: two models can disagree on the same image, which is why the eval compares them against my own judgement.

\- Retries cost money, which is why there's a hard cap of 2.



\### What did I learn?

<!-- TODO: the "effort": "off" bug the agent wrote into my Week 5 spec, and building critique.py test-first (55 tests red, then green) -->



\## Weather (Nadia)



\### What is this?

It takes the event's date, time, and location (from the browser, or a city the user types) and fetches the forecast for that moment from Open-Meteo. If no forecast exists, it says so clearly instead of guessing.



\### Why this choice?

\- \*\*Open-Meteo is free and needs no API key:\*\* no secret to leak, no cost.

\- \*\*Plain code, no AI model:\*\* asking a language model for the weather would invite made-up conditions.

\- \*\*No manual weather entry:\*\* the intent decided the app should use real data or nothing.

\- \*\*The time is interpreted in the event's time zone\*\*, so 7 PM in Hartford means 7 PM Eastern, not wherever the server is.



\### What breaks?

\- \*\*Dates beyond the forecast window\*\* (about two weeks out) have no forecast, so it returns "weather unavailable" and generation continues without it.

\- \*\*Ambiguous city names\*\* (Hartford, Connecticut vs Hartford in the UK).

\- \*\*The user declines location access\*\*, so they type a city instead.

\- \*\*The network or the weather service fails\*\*, which is treated the same as unavailable and doesn't block outfits.

\- \*\*Windows has no time-zone database:\*\* 7 weather tests failed on my machine until I added `tzdata`. It worked on Linux, a real example of "works on my machine."



\### What did I learn?

\- "No data" is more honest than invented data, and the critique leaves weather out of the score rather than penalizing it.

\- The `tzdata` failure showed that environments differ, and tests catch it.



\## Remix (Nadia)



\### What is this?

After seeing three outfits, the user can mix pieces (the shirt from option 1, the trousers from option 3) and type changes like "keep the trousers, swap the jacket." The app generates a new image and gives it a fresh critique against the revised brief.



\### Why this choice?

\- \*\*The original brief carries over\*\* (occasion, styling, weather) unless the user changes it, so the remix doesn't forget the context.

\- \*\*Image-conditioned generation:\*\* the generator receives the chosen pieces as visual references. That's why the spec moved to Google's image model: the original Flux/Recraft models no longer existed on OpenRouter and couldn't do this anyway.

\- \*\*A fresh critique checks that the kept pieces actually stayed the same\*\*, because image models don't guarantee it.

\- \*\*The server reuses the original job's location\*\*, so the weather stays consistent.



\### What breaks?

\- The image model subtly changes a "kept" piece (a different colour or pattern). The critique flags it and retries, up to 2 times.

\- Conflicting choices, like two jackets from different options.

\- Each remix is another generation call, and image generation is about 90% of the project's cost.

\- The revisions strip only lasts for the session unless the user saves the look.



\### What did I learn?

\- Model slugs go stale: half the models named in the plan had disappeared from OpenRouter, so verifying them against the live list matters.

\- "Preserve this piece" is a request to the model, not a guarantee, so the code has to check it.

