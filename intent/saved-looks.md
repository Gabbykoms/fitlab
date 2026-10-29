# FitLab: Save looks for later

Status: Draft — Under review.
Named team approver: Patrick.

## Purpose

Let users keep preferred outfits and return to them after the current session.

## User experience

Users can save a generated or refined look and reopen it later. The saved look includes its image, clothing pieces, brief, and critique so the user can understand the original recommendation.

## Success criteria

Saved looks belong to the user's account and are accessible across sessions and devices, alongside their uploaded wardrobe.

- Users can explicitly save and reopen a look after leaving the session.
- Signing into the same account on another device provides access to saved looks.
- Saving preserves the selected version and its associated critique, including unresolved mismatches.
- The original event and weather context remains labeled as the context used at generation time, not a fresh forecast.
- Users receive confirmation of a successful save or a clear failure message.

## Open decisions

- ~~Whether users can organize, rename, delete, and further refine saved looks in the first version.~~ **Resolved 2026-10-26 (Patrick):** users can view, filter (by occasion and date range), and delete saved looks, with a confirmation step before deleting. Renaming, folders, and remixing a saved look are out of scope for v1. See `spec.md` FE-19, FE-20, and FE-27.
