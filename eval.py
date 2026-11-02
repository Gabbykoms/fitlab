"""Explicit, billed vision-model comparison on existing local outfit images.

Example: python eval.py --cases eval-cases.json --output eval-results.json
Input: [{"image": "path/to/outfit.png", "brief": {...}, "weather": {...},
         "references": ["path/to/garment.png"]}]

Image sets (spec.md section 8.2): python eval.py --imageset imagesets/<set>/manifest.json --output out.json
asks each model a yes/no checklist and a narrow text read per image, checks both in code
(checklist.py), and lists where the first two models disagree.
Nothing runs unless this command is invoked. Supply OPENROUTER_API_KEY in the environment.
"""
import argparse
import asyncio
import json
from pathlib import Path
from checklist import CHECKLIST_PROMPT, TEXT_PROMPT, check_checklist, disagreements, extract_json, text_matches
from critique import critique_image
from media import read_image
from provider import OpenRouter, ProviderError


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


async def ask(provider, prompt, image, model):
    """One vision call. A provider failure becomes a failed answer, never a crash."""
    try:
        text, usage = await provider.vision(prompt, [image], model=model)
        return text, usage, None
    except ProviderError as exc:
        return None, {}, str(exc)


async def checklist_one(provider, model, image, entry):
    items = '\n'.join(f'- {r}' for r in entry['requirements'])
    prompt = CHECKLIST_PROMPT.format(prompt=entry.get('prompt', ''), items=items)
    raw, usage, error = await ask(provider, prompt, image, model)
    critique = extract_json(raw)
    result = {'name': entry['name'], 'model': model, 'critique': critique, 'raw': raw, 'error': error,
              'usage': usage, 'check': check_checklist(entry['requirements'], critique)}
    if entry.get('expected_text'):
        read, text_usage, text_error = await ask(provider, TEXT_PROMPT, image, model)
        result.update(text_read=(read or '').strip(), text_usage=text_usage, text_error=text_error,
                      text_matches=text_matches(entry['expected_text'], read))
    return result


async def evaluate_imageset(manifest_path, models, provider=None):
    provider = provider or OpenRouter()
    if not provider.configured():
        raise SystemExit('Set OPENROUTER_API_KEY before running this billed evaluation.')
    manifest_path = Path(manifest_path)
    results = []
    for entry in json.loads(manifest_path.read_text()):
        image = read_image(manifest_path.parent / entry['file'])
        for model in models:
            results.append(await checklist_one(provider, model, image, entry))
    per_model = [[r for r in results if r['model'] == m] for m in models[:2]]
    diffs = disagreements(*per_model) if len(per_model) == 2 else []
    return {'results': results, 'disagreements': diffs}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--cases')
    source.add_argument('--imageset', help='manifest.json of an image set with requirements')
    parser.add_argument('--output', required=True)
    parser.add_argument('--models', nargs='+', default=['xiaomi/mimo-v2.6-flash', 'minimax/minimax-m3'])
    args = parser.parse_args()
    if args.imageset:
        report = asyncio.run(evaluate_imageset(args.imageset, args.models))
        Path(args.output).write_text(json.dumps(report, indent=2))
        for r in report['results']:
            verdict = 'ok' if r['check']['ok'] else '; '.join(r['check']['problems'])
            text = f"  text read {r['text_read']!r} ({'match' if r['text_matches'] else 'MISMATCH'})" if 'text_read' in r else ''
            print(f"{r['name']} [{r['model']}]: {verdict}{text}")
        print(f"{len(report['disagreements'])} image(s) where the first two models disagree. Look at those yourself.")
    else:
        cases = json.loads(Path(args.cases).read_text())
        results = asyncio.run(evaluate(cases, args.models))
        Path(args.output).write_text(json.dumps(results, indent=2))
        print(f'Wrote {len(results)} critiques. Compare against human judgments and reconcile cost with provider billing.')
