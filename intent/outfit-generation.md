# FitLab: Generate outfit ideas

Status: Draft — under review.
Named team approver: Gabriel.

## Purpose

Help users imagine what to wear for an occasion by generating three invented outfit ideas on fictional mannequins.

## User experience

The user describes their occasion and desired mood or appearance, selects an event date and time, and chooses a styling preference for each request. Masculine styling is one choice, not a fixed app-wide setting. The app uses weather for the event to inform the outfits.

Users must sign in before generating outfits. When they select uploaded clothing, generated looks must preserve those pieces as closely as possible unless changes are explicitly requested.

Example: A senior-year dinner in Hartford, with a relaxed, clean, smart appearance and masculine styling. The app returns three distinct, equally suitable outfit alternatives that meet the same occasion and formality requirements.

Each option displays a generated image and identifies its individual clothing pieces so users can select and combine them later. Users can invent new outfit ideas or upload their own clothing or outfits as references. Users can save looks for later.

## Success criteria

- A valid brief produces three distinguishable, complete outfit ideas that are equally suitable for the brief, rather than a casual-to-dressy range.
- Each outfit is displayed on a fictional mannequin, with identifiable clothing pieces.
- Styling preference can change with every request.
- Occasion, requested aesthetic, and available event weather inform generation.
- Generation failures are explained and can be retried.
- When vision critique finds a mismatch with the brief, the app automatically regenerates the affected option and critiques the new image.

## Boundaries

Uploads are scoped to clothing-only photos, with no images of real people, consistent with the assignment. Generated looks use fictional mannequins. Shopping integrations and virtual try-on are outside the initial scope. The extent of wardrobe organization remains to be decided.

## Open decisions

- Which styling choices and optional fit, color, or clothing restrictions to offer.
