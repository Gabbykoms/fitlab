# Image sets

Generated images with known requirements, for checking the critique path (spec.md section 11).

| Set | What varies | Model | Seeds | Cost |
|---|---|---|---|---|
| `patrick-occasions/` | the occasion (wedding, hike, interview, game day, beach); a placard names it | `black-forest-labs/flux.2-klein-4b` | 601–605 | $0.075 for five |

Each set has `prompts.json` (prompt, seed, yes/no requirements, expected placard text), written by hand, and `manifest.json`, **written by `generate.py`** from `prompts.json` plus model, media type, file, seconds and the cost from the reply. Don't edit a manifest by hand: change `prompts.json` and regenerate.

```bash
python imagesets/generate.py imagesets/<set>/prompts.json --out imagesets/<set>   # billed, needs OPENROUTER_API_KEY
python eval.py --imageset imagesets/<set>/manifest.json --output eval-imageset.json  # billed: checklist + text read per model
```

**Known result for `patrick-occasions`** (open the images in this folder to verify): `occasion-02.jpg` has its placard misspelled **"HIIKE"**. The narrow text read compared in code catches it. Both critics' checklists say "met", and m3's checklist evidence quietly calls it "HIKE". `occasion-01.jpg` shows two fused mannequins, which no requirement covers. Full record: Patrick's Week 6 `CHECKS.md` (`cpsc415-week05/week06`).
