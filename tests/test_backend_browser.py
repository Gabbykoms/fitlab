"""Exercise the frontend against real routes, SQLite, and private image storage."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest
from playwright.sync_api import expect
from fakes import png
from test_browser import sign_up, fill_brief, JOB_TIMEOUT_MS

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def real_server(tmp_path_factory):
    root = tmp_path_factory.mktemp('real-backend')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'FITLAB_DB_PATH': str(root / 'app.db'), 'FITLAB_STORAGE_PATH': str(root)}
    env.pop('OPENROUTER_API_KEY', None)
    proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'real_server:app', '--app-dir', str(ROOT / 'tests'),
                             '--host', '127.0.0.1', '--port', str(port), '--log-level', 'warning'], cwd=ROOT, env=env)
    url = f'http://127.0.0.1:{port}'
    try:
        for _ in range(100):
            try:
                if httpx.get(url + '/api/health', timeout=.2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.1)
        else:
            pytest.fail('real backend did not start')
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_real_backend_full_browser_flow(page, real_server):
    errors, urls = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('request', lambda req: urls.append(req.url))
    username = sign_up(page, real_server)
    page.set_input_files('#file-input', {'name': 'shirt.png', 'mimeType': 'image/png', 'buffer': png()})
    row = page.locator('.upload-row')
    row.locator('select').select_option('top')
    row.locator('.upload-send').click()
    expect(page.locator('.wardrobe-item')).to_have_count(1)
    page.locator('.select-toggle').click()
    fill_brief(page)
    page.click('#generate-btn')
    expect(page.locator('#job-status')).to_contain_text('complete', timeout=JOB_TIMEOUT_MS)
    expect(page.locator('#options .option-card')).to_have_count(3)
    expect(page.locator('#options .overall-readout').first).to_have_text('85')
    page.locator('#options .piece').first.click()
    page.fill('#remix-instructions', 'Keep the shirt')
    page.click('#remix-btn')
    expect(page.locator('#revisions .save-look')).to_be_visible(timeout=JOB_TIMEOUT_MS)
    page.locator('#revisions .save-look').click()
    expect(page.locator('#revisions .save-look')).to_have_text('Saved ✓')
    page.reload()
    expect(page.locator('#user-badge')).to_have_text(username)
    expect(page.locator('.wardrobe-item')).to_have_count(1)
    page.click('#open-saved')
    expect(page.locator('.saved-item')).to_have_count(1)
    page.locator('.delete-look').click()
    page.locator('.confirm-delete').click()
    expect(page.locator('.saved-item')).to_have_count(0)
    assert not errors
    assert all(url.startswith(real_server) or url.startswith(('data:', 'blob:')) for url in urls)
