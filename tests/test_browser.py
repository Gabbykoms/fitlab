"""Browser-driven checks for the FitLab front end (spec.md §3.6, §5 SEC-2, §6).

Runs headless Chromium against dev_server.py (an in-memory stub with no keys and
no network), so it needs neither an API key nor network access.
"""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
FORBIDDEN = ["openrouter", "OPENROUTER_API_KEY", "api_key", "Bearer",
             "google/gemini", "xiaomi/", "minimax/", "openai/", "anthropic/"]
JOB_TIMEOUT_MS = 15_000


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def server_url():
    port = _free_port()
    env = {**os.environ, "FITLAB_STUB_JOB_SECONDS": "1.5"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "dev_server:app", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=env)
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            if httpx.get(f"{url}/api/health", timeout=0.5).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    else:
        proc.kill()
        pytest.fail("dev_server did not start")
    yield url
    proc.terminate()
    proc.wait(timeout=5)


def future(days: int = 3) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def sign_up(page: Page, url: str) -> str:
    username = f"u{uuid.uuid4().hex[:10]}"
    page.goto(url)
    expect(page.locator("#auth-dialog")).to_be_visible()
    page.fill("#auth-username", username)
    page.fill("#auth-password", "correct-horse-1")
    page.click("#register-btn")
    expect(page.locator("#auth-dialog")).to_be_hidden()
    expect(page.locator("#user-badge")).to_contain_text(username)
    return username


def fill_brief(page: Page, occasion: str = "senior-year dinner", city: str = "Hartford") -> None:
    page.fill("#occasion", occasion)
    page.fill("#aesthetic", "relaxed, clean, smart")
    page.check("input[name=styling][value=masculine]")
    page.fill("#event-date", future())
    page.fill("#event-time", "18:00")
    page.fill("#city", city)


def generate(page: Page, **brief) -> None:
    fill_brief(page, **brief)
    page.click("#generate-btn")
    expect(page.locator("#job-status")).to_contain_text(re.compile("complete|failed", re.I),
                                                        timeout=JOB_TIMEOUT_MS)


def upload_png(page: Page, label: str) -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    page.set_input_files("#file-input", files=[{"name": f"{label}.png", "mimeType": "image/png", "buffer": png}])
    row = page.locator(".upload-row").last
    row.locator("select").select_option("top")
    row.locator("input[type=text]").fill(label)
    row.locator("button.upload-send").click()


# ---- key isolation -----------------------------------------------------------

def test_static_sources_contain_no_provider_or_key_strings():
    files = [p for p in STATIC.rglob("*") if p.suffix in {".html", ".js", ".css"}]
    assert files, "no static sources found"
    for path in files:
        text = path.read_text(encoding="utf-8")
        for needle in FORBIDDEN:
            assert needle.lower() not in text.lower(), f"{needle!r} found in {path.relative_to(ROOT)}"


def test_served_sources_contain_no_secrets(server_url):
    for asset in ["/", "/app.js", "/style.css"]:
        body = httpx.get(server_url + asset).text
        for needle in FORBIDDEN:
            assert needle.lower() not in body.lower()


def test_full_flow_stays_same_origin_without_auth_headers(page: Page, server_url):
    seen = []
    page.on("request", lambda r: seen.append((r.url, r.headers)))
    sign_up(page, server_url)
    upload_png(page, "blue shirt")
    expect(page.locator(".wardrobe-item")).to_have_count(1)
    generate(page)
    expect(page.locator(".option-card")).to_have_count(3)
    assert seen
    for url, headers in seen:
        assert url.startswith(server_url) or url.startswith("data:"), f"external request: {url}"
        if "/api/" in url:
            assert "authorization" not in {k.lower() for k in headers}


# ---- auth ----------------------------------------------------------------------

def test_signed_out_shows_auth_dialog_and_server_enforces(page: Page, server_url):
    page.goto(server_url)
    expect(page.locator("#auth-dialog")).to_be_visible()
    expect(page.locator("#wardrobe-panel")).to_be_hidden()
    expect(page.locator("#results-panel")).to_be_hidden()
    assert page.request.get(f"{server_url}/api/wardrobe").status == 401


def test_wrong_password_shows_plain_message(page: Page, server_url):
    username = sign_up(page, server_url)
    page.click("#logout-btn")
    expect(page.locator("#auth-dialog")).to_be_visible()
    page.fill("#auth-username", username)
    page.fill("#auth-password", "wrong-password")
    page.click("#login-btn")
    expect(page.locator("#auth-error")).to_have_text("That username and password do not match.")
    expect(page.locator("#auth-error")).not_to_contain_text("401")


# ---- brief + wardrobe ------------------------------------------------------------

def test_generate_disabled_until_brief_complete(page: Page, server_url):
    sign_up(page, server_url)
    expect(page.locator("#generate-btn")).to_be_disabled()
    fill_brief(page)
    expect(page.locator("#generate-btn")).to_be_enabled()
    page.fill("#event-date", (date.today() - timedelta(days=1)).isoformat())
    expect(page.locator("#generate-btn")).to_be_disabled()


def test_location_line_names_the_city(page: Page, server_url):
    sign_up(page, server_url)
    page.fill("#city", "Hartford")
    expect(page.locator("#location-status")).to_contain_text("Using Hartford")


def test_upload_rule_shown_and_person_rejected(page: Page, server_url):
    sign_up(page, server_url)
    expect(page.locator("#clothing-rule")).to_contain_text("Upload clothing only")
    upload_png(page, "person")
    expect(page.locator(".upload-row .upload-error")).to_contain_text("looks like it shows a person")
    expect(page.locator(".wardrobe-item")).to_have_count(0)


def test_selected_pieces_are_echoed_in_brief(page: Page, server_url):
    sign_up(page, server_url)
    upload_png(page, "green coat")
    page.locator(".wardrobe-item button.select-toggle").first.click()
    expect(page.locator("#selection-echo")).to_contain_text("1 piece selected")


# ---- results ---------------------------------------------------------------------

def test_cards_render_scores_and_attempt_log(page: Page, server_url):
    sign_up(page, server_url)
    generate(page)
    cards = page.locator(".option-card")
    expect(cards).to_have_count(3)
    expect(cards.first.locator(".overall-readout")).to_have_text(re.compile(r"\d+"))
    expect(cards.nth(1).locator(".attempt-log li")).to_have_count(2)
    expect(cards.first.locator(".piece")).not_to_have_count(0)


def test_unassessed_dimensions_say_not_assessed(page: Page, server_url):
    sign_up(page, server_url)
    generate(page, city="nowhere")
    expect(page.locator("#weather-readout")).to_contain_text("without weather guidance")
    weather_rows = page.locator(".option-card .gauge[data-dim=weather]")
    expect(weather_rows).to_have_count(3)
    for i in range(3):
        expect(weather_rows.nth(i)).to_contain_text("Not assessed")
        expect(weather_rows.nth(i)).not_to_contain_text("0%")


def test_exhausted_retries_show_unresolved_banner(page: Page, server_url):
    sign_up(page, server_url)
    generate(page, occasion="dinner unresolved")
    first = page.locator(".option-card").first
    expect(first.locator(".unresolved-banner")).to_be_visible()
    expect(first.locator(".attempt-log li")).to_have_count(3)


def test_failed_critique_is_disclosed(page: Page, server_url):
    sign_up(page, server_url)
    generate(page, occasion="dinner nocritique")
    third = page.locator(".option-card").nth(2)
    expect(third).to_contain_text("could not check this outfit")
    expect(third.locator(".overall-readout")).to_have_count(0)


def test_job_failure_shows_sentence_not_status(page: Page, server_url):
    sign_up(page, server_url)
    generate(page, occasion="fail please")
    toast = page.locator("#toasts .toast").last
    expect(toast).to_contain_text("did not respond properly")
    expect(toast).not_to_contain_text(re.compile(r"\b[45]\d\d\b|\{"))


# ---- remix + saved ------------------------------------------------------------------

def test_remix_requires_chosen_pieces_and_adds_revision(page: Page, server_url):
    sign_up(page, server_url)
    generate(page)
    expect(page.locator("#remix-btn")).to_be_disabled()
    page.locator(".option-card").nth(0).locator(".piece").nth(0).click()
    page.locator(".option-card").nth(2).locator(".piece").nth(1).click()
    expect(page.locator("#remix-chosen li")).to_have_count(2)
    page.fill("#remix-instructions", "Keep the trousers, swap the jacket.")
    expect(page.locator("#remix-btn")).to_be_enabled()
    page.click("#remix-btn")
    expect(page.locator("#revisions .option-card")).to_have_count(1, timeout=JOB_TIMEOUT_MS)


def test_save_filter_and_delete_look(page: Page, server_url):
    sign_up(page, server_url)
    generate(page)
    page.locator(".option-card").first.locator("button.save-look").click()
    expect(page.locator("#toasts .toast").last).to_contain_text("Saved")
    page.click("#open-saved")
    expect(page.locator("#saved-drawer")).to_be_visible()
    expect(page.locator(".saved-item")).to_have_count(1)
    page.fill("#filter-occasion", "no-such-occasion")
    with page.expect_request(re.compile(r"/api/looks\?.*occasion=no-such-occasion")):
        page.click("#filter-apply")
    expect(page.locator(".saved-item")).to_have_count(0)
    page.fill("#filter-occasion", "")
    page.click("#filter-apply")
    page.locator(".saved-item button.delete-look").first.click()
    page.locator(".saved-item button.confirm-delete").first.click()
    expect(page.locator(".saved-item")).to_have_count(0)


def test_usable_at_360px(page: Page, server_url):
    page.set_viewport_size({"width": 360, "height": 800})
    sign_up(page, server_url)
    overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
    assert not overflow
