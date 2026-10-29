"""Real backend account/session checks using an isolated SQLite database."""
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
# Keep direct pytest invocation working without packaging the application.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app import COOKIE, create_app, hasher
import db

CREDS = {'username': 'test-user', 'password': 'correct-horse-1'}


@pytest.fixture
def backend(tmp_path):
    path = tmp_path / 'test.db'
    with TestClient(create_app(path)) as client:
        yield client, path


def sign_in(client):
    assert client.post('/api/auth/register', json=CREDS).status_code == 200
    response = client.post('/api/auth/login', json=CREDS)
    assert response.status_code == 200
    return response


def test_account_persistence_and_password_hash(backend):
    client, path = backend
    sign_in(client)
    user = db.get_user_by_name(path, 'TEST-USER')
    assert user['password_hash'].startswith('$argon2id$')
    assert hasher.verify(user['password_hash'], CREDS['password'])
    token = client.cookies.get(COOKIE)
    with TestClient(create_app(path)) as restarted:
        restarted.cookies.set(COOKIE, token)
        assert restarted.get('/api/auth/me').json()['username'] == CREDS['username']
        assert restarted.post('/api/auth/login', json=CREDS).status_code == 200


def test_duplicate_and_bad_credentials(backend):
    client, _ = backend
    sign_in(client)
    assert client.post('/api/auth/register', json={**CREDS, 'username': 'TEST-USER'}).status_code == 409
    bad = client.post('/api/auth/login', json={**CREDS, 'password': 'wrong-password'})
    absent = client.post('/api/auth/login', json={**CREDS, 'username': 'missing-user'})
    assert bad.status_code == absent.status_code == 401
    assert bad.json() == absent.json()


def test_cookie_rotation_logout_and_replay(backend):
    client, _ = backend
    response = sign_in(client)
    cookie = response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'samesite=lax' in cookie
    old = client.cookies.get(COOKIE)
    client.post('/api/auth/login', json=CREDS)
    new = client.cookies.get(COOKIE)
    assert old != new
    assert client.get('/api/auth/me', headers={'Cookie': f'{COOKIE}={old}'}).status_code == 401
    assert client.post('/api/auth/logout').status_code == 200
    assert client.get('/api/auth/me', headers={'Cookie': f'{COOKIE}={new}'}).status_code == 401


def test_session_expiry_and_sliding_refresh(backend):
    client, path = backend
    sign_in(client)
    token = client.cookies.get(COOKIE)
    with db.connection(path) as conn:
        # Use the timezone-aware format stored by the implementation.
        conn.execute("UPDATE sessions SET expires_at = strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now', '+1 day') WHERE token = ?", (token,))
    assert client.get('/api/auth/me').status_code == 200
    with db.connection(path) as conn:
        expiry = conn.execute('SELECT expires_at FROM sessions WHERE token = ?', (token,)).fetchone()[0]
        from datetime import datetime, timezone
        assert (datetime.fromisoformat(expiry) - datetime.now(timezone.utc)).days >= 29
        conn.execute('UPDATE sessions SET expires_at = ? WHERE token = ?', ('2000-01-01T00:00:00+00:00', token))
    assert client.get('/api/auth/me').status_code == 401


def test_protected_routes_and_static_boundary(backend):
    client, _ = backend
    for route in ['/api/auth/me', '/api/wardrobe', '/api/looks', '/api/future-feature']:
        assert client.get(route).status_code == 401
    assert client.get('/').status_code == 200
    assert client.get('/js/wardrobe.js').status_code == 200
    assert client.get('/app.py').status_code == 404
    assert client.get('/fitlab.db').status_code == 404
    sign_in(client)
    assert client.get('/api/wardrobe').json() == {'items': []}


def test_health_and_validation_do_not_leak_secrets(backend, monkeypatch):
    client, path = backend
    secret = 'provider-secret-for-test'
    monkeypatch.setenv('OPENROUTER_API_KEY', secret)
    response = client.get('/api/health')
    assert response.json()['openrouter_key_configured'] is True
    assert secret not in response.text
    password = 'sensitive-password-' * 20
    response = client.post('/api/auth/register', json={**CREDS, 'password': password})
    assert response.status_code == 422
    assert password not in response.text
    path.unlink()
    assert client.get('/api/health').status_code == 503
    assert not path.exists()


def test_https_cookie(tmp_path):
    with TestClient(create_app(tmp_path / 'secure.db'), base_url='https://testserver') as client:
        response = sign_in(client)
        assert 'secure' in response.headers['set-cookie'].lower()
        assert client.get('/api/auth/me').status_code == 200


def test_accounts_are_isolated(backend):
    client, _ = backend
    sign_in(client)
    first = client.get('/api/auth/me').json()
    client.post('/api/auth/logout')
    second = {**CREDS, 'username': 'second-user'}
    client.post('/api/auth/register', json=second)
    client.post('/api/auth/login', json=second)
    current = client.get('/api/auth/me').json()
    assert current['username'] == 'second-user'
    assert current['user_id'] != first['user_id']
