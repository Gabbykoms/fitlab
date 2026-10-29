"""FitLab API: authenticated styling services and static frontend.

Run one worker with uvicorn app:app. Provider keys remain server-side.
"""
from contextlib import asynccontextmanager
import os
from pathlib import Path
import secrets
import sqlite3

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

import db
from datetime import date
from typing import Annotated
from models import Event, GenerateBody, RemixBody, SaveBody
from services import StylingService, MissingResource
from provider import ProviderError
from media import CATEGORIES, MAX_UPLOAD_BYTES
from limits import UploadBodyLimit

STATIC_DIR = Path(__file__).resolve().parent / 'static'
COOKIE = 'fitlab_session'
PUBLIC_API = {'/api/health', '/api/auth/register', '/api/auth/login'}
hasher = PasswordHasher()
# Verify a real hash even for unknown usernames to avoid a fast missing-user path.
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r'^[A-Za-z0-9_.-]+$')
    password: str = Field(min_length=8, max_length=200)


def create_app(database_path=None, secure_cookies=None, *, storage_path=None, provider=None, weather_resolver=None):
    path = str(database_path or os.environ.get('FITLAB_DB_PATH', './fitlab.db'))
    secure = (os.environ.get('FITLAB_SECURE_COOKIES', '').lower() == 'true'
              if secure_cookies is None else secure_cookies)

    storage = storage_path or os.environ.get('FITLAB_STORAGE_PATH', str(Path(path).resolve().parent))
    styling = StylingService(path, storage, provider, weather_resolver)

    @asynccontextmanager
    async def lifespan(app):
        await run_in_threadpool(db.init_db, path)
        await run_in_threadpool(db.recover_jobs, path)
        try:
            yield
        finally:
            await styling.close()

    app = FastAPI(title='FitLab', version='0.1.0', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url='/api/openapi.json')
    app.state.styling = styling
    app.add_middleware(UploadBodyLimit)

    def set_session_cookie(response, token, request):
        response.set_cookie(COOKIE, token, max_age=db.SESSION_SECONDS,
                            httponly=True, samesite='lax',
                            secure=secure or request.url.scheme == 'https')

    @app.middleware('http')
    async def require_session(request, call_next):
        route = request.url.path.rstrip('/')
        protected = (route == '/api' or route.startswith('/api/')) and route not in PUBLIC_API
        token = request.cookies.get(COOKIE, '')
        if protected:
            try:
                user = await run_in_threadpool(db.get_session_user, path, token)
            except sqlite3.Error:
                return JSONResponse({'detail': 'We could not access your account right now. Please try again.'}, status_code=503)
            if user is None:
                return JSONResponse({'detail': 'authentication required'}, status_code=401)
            request.state.user = user
            request.state.user_id = user['user_id']
        response = await call_next(request)
        if protected and route != '/api/auth/logout':
            set_session_cookie(response, token, request)
        if route == '/api' or route.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # FastAPI's default errors may echo password input; return only safe fields.
        return JSONResponse({'detail': [
            {'loc': list(error['loc']), 'msg': error['msg'], 'type': error['type']}
            for error in exc.errors()
        ]}, status_code=422)

    @app.exception_handler(sqlite3.Error)
    async def database_error(request, exc):
        return JSONResponse({'detail': 'We could not save that right now. Please try again.'}, status_code=500)

    @app.get('/api/health')
    def health():
        if not db.healthy(path):
            return JSONResponse({'status': 'degraded'}, status_code=503)
        return {'status': 'ok', 'database': True,
                'openrouter_key_configured': bool(os.environ.get('OPENROUTER_API_KEY')),
                'weather_key_configured': bool(os.environ.get('WEATHER_API_KEY')),
                'version': app.version}

    @app.post('/api/auth/register')
    def register(body: Credentials):
        try:
            user = db.create_user(path, body.username, hasher.hash(body.password))
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'That username is already taken.') from None
        return {'user_id': user['id'], 'username': user['username'], 'created_at': user['created_at']}

    @app.post('/api/auth/login')
    def login(body: Credentials, request: Request, response: Response):
        user = db.get_user_by_name(path, body.username)
        try:
            hasher.verify(user['password_hash'] if user else DUMMY_HASH, body.password)
        except VerificationError:
            raise HTTPException(401, 'That username and password do not match.') from None
        if not user:
            raise HTTPException(401, 'That username and password do not match.')
        token = secrets.token_urlsafe(32)
        db.create_session(path, user['id'], token, request.cookies.get(COOKIE))
        set_session_cookie(response, token, request)
        return {'user_id': user['id'], 'username': user['username']}

    @app.post('/api/auth/logout')
    def logout(request: Request, response: Response):
        db.delete_session(path, request.cookies.get(COOKIE, ''))
        response.delete_cookie(COOKIE, httponly=True, samesite='lax',
                               secure=secure or request.url.scheme == 'https')
        return {'ok': True}

    @app.get('/api/auth/me')
    def me(request: Request):
        return request.state.user

    @app.exception_handler(MissingResource)
    async def missing_resource(request, exc):
        return JSONResponse({'detail': 'That item is no longer available.'}, status_code=404)

    @app.exception_handler(ProviderError)
    async def provider_error(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=503)

    @app.exception_handler(OSError)
    async def storage_error(request, exc):
        return JSONResponse({'detail': 'We could not access that image right now. Please try again.'}, status_code=503)

    @app.get('/api/wardrobe')
    async def wardrobe(request: Request):
        return {'items': await styling.wardrobe(request.state.user_id)}

    @app.post('/api/wardrobe/upload')
    async def upload(request: Request, file: UploadFile = File(...), category: str = Form(...),
                     label: str = Form('', max_length=80)):
        if category not in CATEGORIES:
            raise HTTPException(422, 'Please choose a clothing category.')
        try:
            data = await file.read(MAX_UPLOAD_BYTES + 1)
        finally:
            await file.close()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, 'That file is larger than 10 MB.')
        try:
            return await styling.upload(request.state.user_id, data, category, label.strip() or None)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.delete('/api/wardrobe/{item_id}')
    async def delete_item(item_id: int, request: Request):
        await styling.delete_item(request.state.user_id, item_id)
        return {'ok': True}

    @app.get('/api/weather')
    async def weather(event: Annotated[Event, Query()]):
        return await styling.weather_resolver(**event.model_dump(mode='json'))

    @app.post('/api/outfits/generate', status_code=202)
    async def generate(body: GenerateBody, request: Request):
        allowed = {styling.provider.critique_model, 'xiaomi/mimo-v2.6-flash', 'minimax/minimax-m3', 'openai/gpt-4o-mini'}
        if body.critique_model is not None and body.critique_model not in allowed:
            raise HTTPException(422, 'Choose a supported critique model.')
        try:
            return await styling.submit(request.state.user_id, body.model_dump(mode='json'))
        except ValueError as exc:
            raise HTTPException(429, str(exc)) from None

    @app.post('/api/outfits/remix', status_code=202)
    async def remix(body: RemixBody, request: Request):
        try:
            return await styling.remix(request.state.user_id, body.model_dump(mode='json'))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get('/api/outfits/{job_id}')
    async def poll(job_id: str, request: Request):
        return await styling.poll(request.state.user_id, job_id)

    @app.post('/api/looks')
    async def save(body: SaveBody, request: Request):
        return {'look': await styling.save(request.state.user_id, body.job_id, body.option_index)}

    @app.get('/api/looks')
    async def looks(request: Request, occasion: str | None = None,
                    from_date: date | None = None, to_date: date | None = None):
        if from_date and to_date and from_date > to_date:
            raise HTTPException(422, 'The from date must be on or before the to date.')
        return {'looks': await styling.looks(request.state.user_id, occasion, from_date, to_date)}

    @app.delete('/api/looks/{look_id}')
    async def delete_look(look_id: int, request: Request):
        if not await styling.call_db(db.delete_look, request.state.user_id, look_id):
            raise MissingResource()
        return {'ok': True}

    @app.api_route('/api/{remaining:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
    def unknown_api(remaining: str):
        raise HTTPException(404, 'That API route is not available.')

    app.mount('/', StaticFiles(directory=STATIC_DIR, html=True), name='static')
    return app


app = create_app()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '8000')))
