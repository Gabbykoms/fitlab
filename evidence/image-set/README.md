# Evidence: Week 6 critique images

This directory holds the offline evidence for the FitLab checklist checker.
The artifacts are produced by the Week 6 lab and copied here by hand; the
checker never reads pixels, so only the manifest and the two critics'
results are required for the offline tests.

## Source

- Images were generated with `black-forest-labs/flux.2-klein-4b`.
- Seeds: 415, 416, 417, 418, 419 (one per image).
- Aspect: 1:1.
- Cost per image: about $0.014.

## Files

- `manifest.json` — five entries (`image-01` through `image-05`). Each
  entry has the generation prompt, the seed, the model slug, the cost,
  and a `requirements` list of four short sentences the prompt asked the
  critic to confirm (for example "the blazer is navy", "the outfit is on
  a mannequin, not a real person").
- `critique.json` — the **cheap model's** results against these five
  images.
- `critique-mimo.json` — the **strong model's** results against these
  five images.

The two critics' results are committed alongside the manifest so the
checklist checker can be exercised against real model output without
billing the API again.

## How the offline tests use this directory

`tests/test_checker.py::test_evidence_manifest_is_well_formed` opens
`manifest.json` and asserts the shape (five entries, four requirements
each). The other five checker tests use hand-built critiques and do not
touch this directory. The checker module itself never reads pixels or
JSON files from here — `check()` takes a parsed critique document and
a list of requirements.

If `manifest.json` is missing, the offline suite goes red with a clear
message naming the expected path. Copy the file from
`../cpsc415-week05/week06/images/manifest.json` to restore the contract.
