from fakes import run_async
import base64
import json
import httpx
import pytest
from provider import OpenRouter, ProviderError
from critique import critique_image
from fakes import png
from media import decode_url


def test_provider_uses_real_pixels_and_server_only_key(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'secret-not-for-clients')
    captured = []
    image = 'data:image/png;base64,' + base64.b64encode(png()).decode()
    def handler(request):
        captured.append((str(request.url), json.loads(request.content), dict(request.headers)))
        if request.url.path.endswith('/images'):
            return httpx.Response(200, json={'data': [{'b64_json': image.split(',')[1], 'media_type': 'image/png'}],
                                             'usage': {'cost': .01}})
        return httpx.Response(200, json={'choices': [{'message': {'content': '{}'}}], 'usage': {}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = OpenRouter(client)
            output, usage = await provider.image('prompt', [image], 42)
            assert decode_url(output)[0] == png()
            assert usage['cost_usd'] == .01
            result = await critique_image(provider, image, {}, {'available': False}, [image])
            assert result['status'] == 'failed'
    run_async(run)
    assert captured[0][0] == 'https://openrouter.ai/api/v1/images'
    assert captured[0][1]['input_references'][0]['image_url']['url'] == image
    body = captured[1][1]
    assert body['reasoning'] == {'enabled': False}
    content = body['messages'][0]['content']
    assert [part['image_url']['url'] for part in content if part['type'] == 'image_url'] == [image, image]
    assert captured[0][2]['authorization'] == 'Bearer secret-not-for-clients'
    assert 'secret-not-for-clients' not in json.dumps(body)


@pytest.mark.parametrize('status', [401, 429, 500])
def test_provider_errors_do_not_echo_response_or_key(monkeypatch, status):
    monkeypatch.setenv('OPENROUTER_API_KEY', 'very-secret')
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda r: httpx.Response(status, json={'error': 'very-secret upstream error'}))) as client:
            with pytest.raises(ProviderError) as exc:
                await OpenRouter(client).vision('test', [])
            assert 'very-secret' not in str(exc.value)
    run_async(run)
