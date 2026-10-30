"""Explicit, billed vision-model comparison on existing local outfit images.

Example: python eval.py --cases eval-cases.json --output eval-results.json
Input: [{"image": "path/to/outfit.png", "brief": {...}, "weather": {...},
         "references": ["path/to/garment.png"]}]
Nothing runs unless this command is invoked. Supply OPENROUTER_API_KEY in the environment.
"""
import argparse
import asyncio
import json
from pathlib import Path
from critique import critique_image
from media import read_image
from provider import OpenRouter


async def evaluate(cases, models):
    provider = OpenRouter()
    if not provider.configured():
        raise SystemExit('Set OPENROUTER_API_KEY before running this billed evaluation.')
    results = []
    for index, case in enumerate(cases):
        image = read_image(case['image'])
        refs = [read_image(path) for path in case.get('references', [])]
        for model in models:
            result = await critique_image(provider, image, case['brief'], case.get('weather', {'available': False}), refs, model=model)
            results.append({'case': index, 'model': model, 'critique': result})
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--models', nargs='+', default=['xiaomi/mimo-v2.6-flash', 'minimax/minimax-m3'])
    args = parser.parse_args()
    cases = json.loads(Path(args.cases).read_text())
    results = asyncio.run(evaluate(cases, args.models))
    Path(args.output).write_text(json.dumps(results, indent=2))
    print(f'Wrote {len(results)} critiques. Compare against human judgments and reconcile cost with provider billing.')
