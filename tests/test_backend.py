import asyncio
from datetime import date, timedelta
import json
from pathlib import Path
import time

import pytest
from fastapi.testclient import TestClient
from app import create_app
import db
from critique import run_option_with_retry
from fakes import FakeProvider, fake_weather, png

CREDS = {'username': 'alice', 'password': 'correct-horse-1'}


def login(client, username='alice'):
    body = {**CREDS, 'username': username}
    client.post('/api/auth/register', json=body)
    assert client.post('/api/auth/login', json=body).status_code == 200


@pytest.fixture
def backend(tmp_path):
    provider = FakeProvider()
    app = create_app(tmp_path / 'test.db', storage_path=tmp_path, provider=provider, weather_resolver=fake_weather)
    with TestClient(app) as client:
        login(client)
        yield client, provider, tmp_path


def brief():
    return {'occasion': 'Dinner', 'aesthetic': 'Clean', 'styling_preference': 'unisex',
            'event_date': (date.today() + timedelta(days=1)).isoformat(), 'event_time': '18:00',
            'selected_item_ids': []}


def upload(client, data=None):
    return client.post('/api/wardrobe/upload', files={'file': ('../../photo.jpg', data or png(), 'image/jpeg')},
                       data={'category': 'top', 'label': 'My shirt'})


def wait_job(client, job_id):
    for _ in range(100):
        response = client.get('/api/outfits/' + job_id)
        assert response.status_code == 200
        job = response.json()
        if job['status'] in ('complete', 'failed'):
            return job
        time.sleep(.02)
    pytest.fail('job did not terminate')


def test_upload_validation_dedup_and_private_storage(backend):
    client, provider, root = backend
    response = upload(client)
    assert response.status_code == 200, response.text
    item = response.json()['item']
    assert item['image_data_url'].startswith('data:image/png;')
    assert 'upload_path' not in item
    assert upload(client).status_code == 422
    assert upload(client, b'not an image').status_code == 422
    assert len(list((root / 'uploads').iterdir())) == 1
    provider.reject = True
    response = upload(client, png('red'))
    assert response.json()['rejected'] is True
    assert len(list((root / 'uploads').iterdir())) == 1
    login(client, 'bob')
    assert client.get('/api/wardrobe').json()['items'] == []
    assert client.delete(f"/api/wardrobe/{item['id']}").status_code == 404
    assert client.post('/api/outfits/generate', json={**brief(), 'selected_item_ids': [item['id']]}).status_code == 404
    login(client)
    assert client.delete(f"/api/wardrobe/{item['id']}").status_code == 200
    assert list((root / 'uploads').iterdir()) == []


def test_full_generate_remix_save_filter_and_ownership(backend):
    client, provider, root = backend
    item = upload(client).json()['item']
    request = {**brief(), 'selected_item_ids': [item['id']]}
    response = client.post('/api/outfits/generate', json=request)
    assert response.status_code == 202, response.text
    job_id = response.json()['job_id']
    job = wait_job(client, job_id)
    assert job['status'] == 'complete', job
    assert len(job['options']) == 3
    assert all(o['critique']['scores']['weather'] is None for o in job['options'])
    assert all(o['critique']['scores']['upload_fidelity'] == 85 for o in job['options'])
    assert len(list((root / 'renders').iterdir())) == 3
    assert 'image_path' not in job['options'][0]
    saved = client.post('/api/looks', json={'job_id': job_id, 'option_index': 0}).json()['look']
    assert saved['critique'] == job['options'][0]['critique']
    assert client.get('/api/looks?occasion=dinn').json()['looks'][0]['id'] == saved['id']
    assert client.get('/api/looks?occasion=other').json()['looks'] == []
    payload = {'source_job_id': job_id, 'selected_pieces': [job['options'][0]['pieces'][0]],
               'instructions': 'Keep this shirt', 'event_date': request['event_date'], 'event_time': '18:00'}
    response = client.post('/api/outfits/remix', json=payload)
    assert response.status_code == 202, response.text
    remixed = wait_job(client, response.json()['job_id'])
    assert remixed['status'] == 'complete'
    assert len(remixed['options']) == 1
    assert 'Keep this shirt' in provider.images[-1][0]
    assert client.post('/api/outfits/remix', json={**payload, 'selected_pieces': [{'id': 'fake'}]}).status_code == 422
    login(client, 'bob')
    assert client.get('/api/outfits/' + job_id).status_code == 404
    assert client.get('/api/looks').json()['looks'] == []
    assert client.delete('/api/looks/' + str(saved['id'])).status_code == 404
    assert client.post('/api/outfits/remix', json=payload).status_code == 404
    login(client)
    assert client.delete('/api/looks/' + str(saved['id'])).status_code == 200
    assert client.get('/api/looks').json()['looks'] == []


def test_retry_ceiling_and_failed_critique_do_not_loop(backend):
    client, provider, _ = backend
    provider.low = True
    response = client.post('/api/outfits/generate', json=brief())
    job = wait_job(client, response.json()['job_id'])
    assert len(provider.images) == 9
    assert all(o['attempts'] == 3 and o['unresolved'] for o in job['options'])
    assert len({entry[2] for entry in provider.images}) == 9
    provider.images.clear()
    provider.bad_critique = True
    job_id = client.post('/api/outfits/generate', json=brief()).json()['job_id']
    job = wait_job(client, job_id)
    assert len(provider.images) == 3
    assert all(o['critique']['status'] == 'failed' for o in job['options'])


def test_restart_recovery_and_saved_persistence(backend):
    client, _, root = backend
    user_id = client.get('/api/auth/me').json()['user_id']
    job = wait_job(client, client.post('/api/outfits/generate', json=brief()).json()['job_id'])
    client.post('/api/looks', json={'job_id': job['job_id'], 'option_index': 1})
    orphan = db.create_job(root / 'test.db', user_id, 'generate', brief())
    with TestClient(create_app(root / 'test.db', storage_path=root, provider=FakeProvider())) as restarted:
        login(restarted)
        assert restarted.get('/api/outfits/' + orphan).json()['status'] == 'failed'
        assert len(restarted.get('/api/looks').json()['looks']) == 1


def test_missing_key_and_invalid_inputs(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    with TestClient(create_app(tmp_path / 'db', storage_path=tmp_path)) as client:
        login(client)
        assert client.post('/api/outfits/generate', json=brief()).status_code == 503
        for changes in [{'event_time': '25:99'}, {'lat': 91, 'lon': 0}, {'occasion': ' '}, {'lat': 12}]:
            assert client.post('/api/outfits/generate', json={**brief(), **changes}).status_code == 422
        assert client.get('/api/looks?from_date=2026-10-20&to_date=2026-10-01').status_code == 422
        assert list(tmp_path.glob('renders/*')) == []


def test_generation_failure_terminates(backend):
    client, provider, _ = backend
    provider.no_images = True
    job = wait_job(client, client.post('/api/outfits/generate', json=brief()).json()['job_id'])
    assert job['status'] == 'failed'
    assert job['error'] and job['options'] == []


def test_upload_cap_and_no_file_after_rejection(backend):
    client, provider, root = backend
    response = upload(client, b'x' * (10 * 1024 * 1024 + 1))
    assert response.status_code == 413
    assert not provider.visions
    assert not list(root.glob('uploads/*'))


def test_partial_generation_keeps_original_indexes(backend):
    client, provider, _ = backend
    original = provider.image
    async def partial(prompt, references, seed):
        from provider import ProviderError
        if 'Option 2.' in prompt:
            raise ProviderError('unavailable')
        return await original(prompt, references, seed)
    provider.image = partial
    job = wait_job(client, client.post('/api/outfits/generate', json=brief()).json()['job_id'])
    assert [o['index'] for o in job['options']] == [0, 2]
    response = client.post('/api/looks', json={'job_id': job['job_id'], 'option_index': 2})
    assert response.status_code == 200
    assert response.json()['look']['option_index'] == 2


def test_missing_image_keeps_critique_visible(backend):
    client, _, root = backend
    job = wait_job(client, client.post('/api/outfits/generate', json=brief()).json()['job_id'])
    for image in (root / 'renders').iterdir():
        image.unlink()
    current = client.get('/api/outfits/' + job['job_id']).json()
    assert current['options'][0]['image_data_url'] == ''
    assert current['options'][0]['critique']['overall'] == 85


def test_remix_uses_source_image_without_claiming_upload_fidelity(backend):
    client, provider, _ = backend
    job = wait_job(client, client.post('/api/outfits/generate', json=brief()).json()['job_id'])
    request = {'source_job_id': job['job_id'], 'selected_pieces': [job['options'][0]['pieces'][0]],
               'instructions': 'Keep it', 'event_date': brief()['event_date'], 'event_time': '18:00'}
    remix = wait_job(client, client.post('/api/outfits/remix', json=request).json()['job_id'])
    assert len(provider.images[-1][1]) == 1
    assert remix['options'][0]['critique']['upload_fidelity_assessed'] is False


def test_remix_reference_limit_is_explicit(backend, monkeypatch):
    from unittest.mock import AsyncMock
    from fakes import run_async
    client, provider, _ = backend
    service = client.app.state.styling
    monkeypatch.setattr(service, 'references', AsyncMock(return_value=['image'] * 12))
    async def run():
        with pytest.raises(ValueError, match='too many image references'):
            await service.submit(1, brief(), 'remix', source_images=['source'] * 3)
    run_async(run)
    assert not provider.images
