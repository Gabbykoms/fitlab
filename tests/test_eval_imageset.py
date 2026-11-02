"""No-key tests for eval.py --imageset (spec.md 11.2): the checklist path with a fake provider."""
import io
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import eval as evaluation  # noqa: E402
from PIL import Image  # noqa: E402
from fakes import run_async  # noqa: E402 (FitLab's helper: safe when another test left a loop running)



class FakeProvider:
    """Answers like a model would, without a network call. One reply per (model, question kind)."""

    def __init__(self, replies):
        self.replies, self.calls = replies, []

    def configured(self):
        return True

    async def vision(self, prompt, images, model=None):
        kind = 'text' if 'exactly as printed' in prompt else 'checklist'
        self.calls.append((model, kind))
        return self.replies[(model, kind)], {'prompt_tokens': 1, 'completion_tokens': 1, 'cost_usd': 0.0}


def png_bytes():
    buffer = io.BytesIO()
    Image.new('RGB', (8, 8), 'white').save(buffer, format='PNG')
    return buffer.getvalue()


def make_set(tmp_path):
    (tmp_path / 'occasion-02.png').write_bytes(png_bytes())
    manifest = [{'name': 'occasion-02', 'file': 'occasion-02.png', 'media_type': 'image/png',
                 'requirements': ['There is a placard'], 'expected_text': 'HIKE'}]
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    return path


def test_imageset_checks_each_model_and_reports_disagreements(tmp_path):
    ok = '{"checks": [{"requirement": "There is a placard", "met": true}]}'
    provider = FakeProvider({('m3', 'checklist'): ok, ('m3', 'text'): 'HIIKE',
                             ('mimo', 'checklist'): 'not json at all', ('mimo', 'text'): 'HIKE'})
    report = run_async(lambda: evaluation.evaluate_imageset(make_set(tmp_path), ['m3', 'mimo'], provider))
    by_model = {r['model']: r for r in report['results']}
    assert by_model['m3']['check']['ok'] and by_model['m3']['text_matches'] is False
    assert not by_model['mimo']['check']['ok'] and by_model['mimo']['text_matches'] is True
    assert report['disagreements'][0]['name'] == 'occasion-02'
    assert len(provider.calls) == 4                   # one checklist and one text read per model
    assert report['compared_models'] == ['m3', 'mimo']


def test_imageset_without_key_stops_before_any_call(tmp_path):
    class NoKey(FakeProvider):
        def configured(self):
            return False
    provider = NoKey({})
    with pytest.raises(SystemExit, match='OPENROUTER_API_KEY'):
        run_async(lambda: evaluation.evaluate_imageset(make_set(tmp_path), ['m3'], provider))
    assert provider.calls == []


def test_real_provider_without_key_stops_before_any_call(tmp_path, monkeypatch):
    """H-1 with the real provider class: no key means configured() is False and nothing is sent."""
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    real = evaluation.OpenRouter()
    assert real.configured() is False

    async def no_network(*args, **kwargs):
        raise AssertionError('a vision call was made without a key')
    monkeypatch.setattr(real, 'vision', no_network)
    with pytest.raises(SystemExit, match='OPENROUTER_API_KEY'):
        run_async(lambda: evaluation.evaluate_imageset(make_set(tmp_path), ['m3'], real))


def test_one_model_runs_without_a_comparison(tmp_path):
    ok = '{"checks": [{"requirement": "There is a placard", "met": true}]}'
    provider = FakeProvider({('m3', 'checklist'): ok, ('m3', 'text'): 'HIKE'})
    report = run_async(lambda: evaluation.evaluate_imageset(make_set(tmp_path), ['m3'], provider))
    assert report['disagreements'] == [] and report['compared_models'] == []
    assert report['results'][0]['check']['ok'] and report['results'][0]['text_matches']
