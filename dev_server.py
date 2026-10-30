"""Dev-only stub of the FitLab API (spec.md §3.1).

Serves static/ and implements every /api/* route in memory with fake images and
critiques from dev_fixtures.py. It holds no keys and makes no network calls, so
the front end can be built and Playwright-tested before app.py exists.

Run:  uvicorn dev_server:app --reload
Edge cases, triggered by keywords:
  city "nowhere"                -> weather unavailable (LOCATION_NOT_FOUND)
  occasion contains "fail"      -> the job fails
  occasion contains "unresolved"-> option A exhausts its retries
  occasion contains "nocritique"-> option C's critique fails (§7.8)
  upload label/filename "person"-> upload rejected by the people check
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import dev_fixtures as fx

STATIC_DIR = Path(__file__).parent / "static"
SESSION_COOKIE = "fitlab_session"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
CATEGORIES = {"top", "bottom", "outerwear", "shoes", "accessory", "full_outfit"}
JOB_SECONDS = float(os.environ.get("FITLAB_STUB_JOB_SECONDS", "6"))
PUBLIC_API = {"/api/health", "/api/auth/register", "/api/auth/login"}
IMAGE_MAGIC = {b"\x89PNG": "image/png", b"\xff\xd8\xff": "image/jpeg", b"GIF8": "image/gif", b"RIFF": "image/webp"}

app = FastAPI(title="FitLab dev stub")

# In-memory tables. Rows are replaced, never edited in place.
DB: dict[str, dict] = {"users": {}, "sessions": {}, "wardrobe": {}, "jobs": {}, "looks": {}}
COUNTERS = {"user": 0, "item": 0, "look": 0}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _next_id(kind: str) -> int:
    COUNTERS[kind] += 1
    return COUNTERS[kind]


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


@app.middleware("http")
async def require_session(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path not in PUBLIC_API:
        user_id = DB["sessions"].get(request.cookies.get(SESSION_COOKIE, ""))
        if user_id is None:
            return JSONResponse({"detail": "authentication required"}, status_code=401)
        request.state.user_id = user_id
    return await call_next(request)


# ---- auth -------------------------------------------------------------------

class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=200)


@app.get("/api/health")
def health():
    return {"status": "ok", "database": True, "openrouter_key_configured": False,
            "weather_key_configured": False, "version": "dev-stub"}


@app.post("/api/auth/register")
def register(body: Credentials):
    key = body.username.lower()
    if key in DB["users"]:
        raise HTTPException(409, "That username is already taken.")
    salt = secrets.token_hex(8)
    user = {"user_id": _next_id("user"), "username": body.username, "created_at": _now(),
            "salt": salt, "password_hash": _hash(body.password, salt)}
    DB["users"] = {**DB["users"], key: user}
    return {k: user[k] for k in ("user_id", "username", "created_at")}


@app.post("/api/auth/login")
def login(body: Credentials, response: Response):
    user = DB["users"].get(body.username.lower())
    if not user or not secrets.compare_digest(user["password_hash"], _hash(body.password, user["salt"])):
        raise HTTPException(401, "That username and password do not match.")
    token = secrets.token_urlsafe(32)
    DB["sessions"] = {**DB["sessions"], token: user["user_id"]}
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=30 * 86400)
    return {"user_id": user["user_id"], "username": user["username"]}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE, "")
    DB["sessions"] = {t: u for t, u in DB["sessions"].items() if t != token}
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/api/auth/me")
def me(request: Request):
    user = next(u for u in DB["users"].values() if u["user_id"] == request.state.user_id)
    return {"user_id": user["user_id"], "username": user["username"]}


# ---- wardrobe ---------------------------------------------------------------

def _owned(table: str, key, user_id: int) -> dict:
    row = DB[table].get(key)
    if row is None or row["user_id"] != user_id:
        raise HTTPException(404, "That item is no longer available.")
    return row


def _public(row: dict) -> dict:
    return {k: v for k, v in row.items() if k != "user_id"}


@app.get("/api/wardrobe")
def list_wardrobe(request: Request):
    uid = request.state.user_id
    return {"items": [_public(r) for r in DB["wardrobe"].values() if r["user_id"] == uid]}


def _rejected(code: str, reason: str) -> dict:
    return {"item": None, "rejected": True, "reason": reason, "code": code}


@app.post("/api/wardrobe/upload")
async def upload(request: Request, file: UploadFile = File(...), category: str = Form(...),
                 label: str = Form("")):
    if category not in CATEGORIES:
        raise HTTPException(422, "Please choose a clothing category.")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "That file is larger than 10 MB.")
    mime = next((m for magic, m in IMAGE_MAGIC.items() if data.startswith(magic)), None)
    if mime is None:
        return _rejected("UNSUPPORTED_TYPE", "That file is not a supported image. Please upload a PNG, JPEG, WebP or GIF.")
    if "person" in f"{label} {file.filename}".lower():
        return _rejected("PERSON_DETECTED", "That photo looks like it shows a person. Please upload clothing "
                                            "only — a flat lay or a piece on a hanger.")
    item = {"id": _next_id("item"), "user_id": request.state.user_id, "category": category,
            "label": label.strip()[:80] or None, "created_at": _now(),
            "image_data_url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}
    DB["wardrobe"] = {**DB["wardrobe"], item["id"]: item}
    return {"item": _public(item), "rejected": False}


@app.delete("/api/wardrobe/{item_id}")
def delete_item(item_id: int, request: Request):
    _owned("wardrobe", item_id, request.state.user_id)
    DB["wardrobe"] = {k: v for k, v in DB["wardrobe"].items() if k != item_id}
    return {"ok": True}


# ---- weather, generation, remix --------------------------------------------

class GenerateBody(BaseModel):
    occasion: str = Field(min_length=1, max_length=200)
    aesthetic: str = Field(min_length=1, max_length=200)
    styling_preference: str = Field(pattern=r"^(masculine|feminine|unisex)$")
    event_date: date
    event_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    city: str | None = Field(default=None, max_length=120)
    lat: float | None = None
    lon: float | None = None
    selected_item_ids: list[int] = []
    notes: str | None = Field(default=None, max_length=1000)


class RemixBody(BaseModel):
    source_job_id: str
    selected_pieces: list[dict] = Field(min_length=1, max_length=12)
    instructions: str = Field(default="", max_length=1000)
    event_date: date
    event_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    city: str | None = Field(default=None, max_length=120)


@app.get("/api/weather")
def weather(event_date: date, event_time: str, city: str | None = None,
            lat: float | None = None, lon: float | None = None):
    return fx.make_weather(event_date.isoformat(), event_time, city, lat, lon)


def _scenario(occasion: str) -> str:
    text = occasion.lower()
    return next((s for s in ("fail", "unresolved", "nocritique") if s in text), "normal")


def _store_job(user_id: int, kind: str, brief: dict, weather_row: dict, options: list, error: str | None) -> str:
    job_id = secrets.token_hex(8)
    job = {"job_id": job_id, "user_id": user_id, "kind": kind, "brief": brief, "weather": weather_row,
           "options": options, "error": error, "started": time.monotonic()}
    DB["jobs"] = {**DB["jobs"], job_id: job}
    return job_id


@app.post("/api/outfits/generate", status_code=202)
def generate(body: GenerateBody, request: Request):
    if body.event_date < date.today():
        raise HTTPException(422, "The event date cannot be in the past.")
    uid = request.state.user_id
    brief = body.model_dump(mode="json")
    weather_row = fx.make_weather(brief["event_date"], body.event_time, body.city, body.lat, body.lon)
    scenario = _scenario(body.occasion)
    has_refs = any(DB["wardrobe"].get(i, {}).get("user_id") == uid for i in body.selected_item_ids)
    options = [] if scenario == "fail" else [
        fx.make_option(i, scenario, weather_row["available"], has_refs) for i in range(3)]
    error = "The image service did not respond properly. Please try again." if scenario == "fail" else None
    return {"job_id": _store_job(uid, "generate", brief, weather_row, options, error), "status": "queued"}


@app.post("/api/outfits/remix", status_code=202)
def remix(body: RemixBody, request: Request):
    uid = request.state.user_id
    source = _owned("jobs", body.source_job_id, uid)
    brief = {**source["brief"], "revision_instructions": body.instructions, "city": body.city,
             "event_date": body.event_date.isoformat(), "event_time": body.event_time}
    weather_row = fx.make_weather(brief["event_date"], body.event_time, body.city,
                                  brief.get("lat"), brief.get("lon"))
    preserved = [{k: p.get(k) for k in ("name", "category", "color", "pattern")} for p in body.selected_pieces]
    option = {**fx.make_option(len(DB["jobs"]) % 3, "normal", weather_row["available"], False, preserved),
              "index": 0, "pieces": fx.make_pieces(0, preserved)[4:]}
    return {"job_id": _store_job(uid, "remix", brief, weather_row, [option], None), "status": "queued"}


def _job_status(job: dict) -> str:
    elapsed = time.monotonic() - job["started"]
    if elapsed < JOB_SECONDS * 0.2:
        return "queued"
    if elapsed < JOB_SECONDS:
        return "running"
    return "failed" if job["error"] else "complete"


@app.get("/api/outfits/{job_id}")
def poll(job_id: str, request: Request):
    job = _owned("jobs", job_id, request.state.user_id)
    status = _job_status(job)
    done = status == "complete"
    return {"job_id": job_id, "status": status, "options": job["options"] if done else [],
            "weather": job["weather"], "error": job["error"] if status == "failed" else None}


# ---- saved looks -------------------------------------------------------------

class SaveBody(BaseModel):
    job_id: str
    option_index: int = Field(ge=0, le=2)


@app.post("/api/looks")
def save_look(body: SaveBody, request: Request):
    uid = request.state.user_id
    job = _owned("jobs", body.job_id, uid)
    if _job_status(job) != "complete" or body.option_index >= len(job["options"]):
        raise HTTPException(404, "That look is no longer available.")
    opt = job["options"][body.option_index]
    look = {"id": _next_id("look"), "user_id": uid, "job_id": body.job_id, "option_index": body.option_index,
            "kind": job["kind"], "occasion": job["brief"]["occasion"], "event_date": job["brief"]["event_date"],
            "event_time": job["brief"]["event_time"], "image_data_url": opt["image_data_url"],
            "pieces": opt["pieces"], "brief": job["brief"], "critique": opt["critique"],
            "weather": job["weather"], "unresolved": opt["unresolved"], "created_at": _now()}
    DB["looks"] = {**DB["looks"], look["id"]: look}
    return {"look": _public(look)}


@app.get("/api/looks")
def list_looks(request: Request, occasion: str | None = None,
               from_date: date | None = None, to_date: date | None = None):
    uid = request.state.user_id
    rows = [r for r in DB["looks"].values() if r["user_id"] == uid]
    if occasion:
        rows = [r for r in rows if occasion.lower() in r["occasion"].lower()]
    if from_date:
        rows = [r for r in rows if r["event_date"] >= from_date.isoformat()]
    if to_date:
        rows = [r for r in rows if r["event_date"] <= to_date.isoformat()]
    return {"looks": [_public(r) for r in sorted(rows, key=lambda r: r["created_at"], reverse=True)]}


@app.delete("/api/looks/{look_id}")
def delete_look(look_id: int, request: Request):
    _owned("looks", look_id, request.state.user_id)
    DB["looks"] = {k: v for k, v in DB["looks"].items() if k != look_id}
    return {"ok": True}


# ---- static -------------------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")
