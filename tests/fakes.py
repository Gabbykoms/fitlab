"""Offline provider contract doubles; never imported by production code."""
import base64
from io import BytesIO
import json
from PIL import Image
from provider import ProviderError
from weather import unavailable


def png(color='navy'):
    stream = BytesIO()
    Image.new('RGB', (24, 32), color).save(stream, format='PNG')
    return stream.getvalue()


class FakeProvider:
    image_model = 'test/image'
    critique_model = 'test/vision'

    def __init__(self):
        self.images = []
        self.visions = []
        self.low = False
        self.reject = False
        self.bad_critique = False
        self.no_images = False

    def configured(self): return True

    async def image(self, prompt, references, seed):
        self.images.append((prompt, references, seed))
        if self.no_images:
            raise ProviderError('unavailable')
        return 'data:image/png;base64,' + base64.b64encode(png()).decode(), {'cost_usd': .01}

    async def vision(self, prompt, images, model=None):
        self.visions.append((prompt, images, model))
        if 'contains_person' in prompt:
            value = {'contains_person': self.reject, 'clothing_only': not self.reject}
        elif '"pieces"' in prompt:
            value = {'pieces': [{'name': 'navy shirt', 'category': 'top', 'color': 'navy', 'pattern': None}]}
        else:
            if self.bad_critique:
                return 'broken json', {'cost_usd': .001}
            weather_available = '"weather_assessed": true' in prompt
            refs = len(images) > 1
            score = 40 if self.low else 85
            value = {'schema_version': '1.0', 'attempt': 1, 'model': model or self.critique_model,
                'scores': {'occasion': score, 'aesthetic': score, 'styling': score,
                           'weather': score if weather_available else None, 'upload_fidelity': score if refs else None},
                'overall': score, 'summary': 'The visible outfit matches the brief.', 'matches': [],
                'mismatches': [], 'uncertainty': ['Fabric warmth cannot be established.'],
                'weather_assessed': weather_available, 'upload_fidelity_assessed': refs,
                'retry_recommended': self.low, 'retry_reason': 'low score' if self.low else ''}
        return json.dumps(value), {'cost_usd': .001}


async def fake_weather(**kwargs):
    return unavailable(**kwargs)


def run_async(factory):
    """Keep async unit tests independent of Playwright's session event loop."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(factory())).result()
