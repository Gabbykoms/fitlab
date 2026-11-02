"""Checklist critique checker (spec.md section 11.1). Pure functions: no model, no key, no network.

The critic is a model, so its answer is data to check, not a verdict. This module can say
whether the critic answered every requirement, answered only those, and said each was met,
and whether the text it read back matches the text the brief asked for. It cannot say
whether the critic was right; a second model and a person looking do that.
"""
import json
import re

NOT_A_CHECKLIST = 'critique was not the JSON checklist that was asked for'

CHECKLIST_PROMPT = """You are checking a generated image against the prompt that produced it.
Prompt: {prompt}

Answer every item below with true or false, strictly from what is visible in the image.
Reply with one JSON object and nothing else:
{{"checks": [{{"requirement": "<item text, copied exactly>", "met": true, "evidence": "<one short sentence>"}}]}}

Items:
{items}"""

TEXT_PROMPT = ('Read the text printed on the placard or sign in this image exactly as printed, '
               'character for character. Reply with that text only. If there is no placard, reply NONE.')


def extract_json(text):
    """The JSON object inside a reply (bare, fenced, or wrapped in prose), or None."""
    if not text:
        return None
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def normalize(text):
    """Lower case, punctuation and extra spaces removed; letters and digits kept."""
    return re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()


def _answers(critique):
    return {normalize(c['requirement']): c for c in critique.get('checks') or []
            if isinstance(c, dict) and isinstance(c.get('requirement'), str)}


def check_checklist(requirements, critique):
    """Compare the critic's checklist with the requirements it was given (G-1, G-3, G-4, G-5)."""
    if critique is None or not isinstance(critique.get('checks'), list):
        return {'ok': False, 'problems': [NOT_A_CHECKLIST], 'unmet': [],
                'missing': list(requirements), 'extra': []}
    answered = _answers(critique)
    wanted = {normalize(r): r for r in requirements}
    missing = [r for key, r in wanted.items() if key not in answered]
    extra = [c['requirement'] for key, c in answered.items() if key not in wanted]
    unmet = [r for key, r in wanted.items() if key in answered and answered[key].get('met') is not True]
    problems = []
    if missing:
        problems.append(f'critic did not answer {len(missing)} requirement(s)')
    if extra:
        problems.append(f'critic answered {len(extra)} item(s) that were not asked')
    if unmet:
        problems.append(f'{len(unmet)} requirement(s) reported unmet')
    return {'ok': not problems, 'problems': problems, 'unmet': unmet, 'missing': missing, 'extra': extra}


def text_matches(expected, read):
    """True when the text read back is the expected text, ignoring case and punctuation (G-6)."""
    return bool(read) and normalize(expected) == normalize(read)


def disagreements(a, b):
    """Images where two critique lists differ on any requirement or on the text read (G-7)."""
    by_name = {entry['name']: entry for entry in b}
    out = []
    for entry_a in a:
        entry_b = by_name.get(entry_a['name'])
        if entry_b is None:
            continue
        answers_a, answers_b = _answers(entry_a.get('critique') or {}), _answers(entry_b.get('critique') or {})
        diffs = []
        for key in sorted(set(answers_a) | set(answers_b)):
            met_a = answers_a.get(key, {}).get('met')
            met_b = answers_b.get(key, {}).get('met')
            if met_a != met_b:
                label = (answers_a.get(key) or answers_b[key])['requirement']
                diffs.append({'requirement': label, 'a': met_a, 'b': met_b})
        if entry_a.get('text_read') != entry_b.get('text_read'):
            diffs.append({'requirement': '<text read>', 'a': entry_a.get('text_read'), 'b': entry_b.get('text_read')})
        if diffs:
            out.append({'name': entry_a['name'], 'diffs': diffs})
    return out
