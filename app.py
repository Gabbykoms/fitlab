"""FitLab API: persistent accounts, sessions, health, and static frontend.

Run with uvicorn app:app --reload. Styling services are not implemented yet.
"""
from contextlib import asynccontextmanager
import os
from pathlib import Path
import secrets
import sqlite3

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

import db

STATIC_DIR = Path(__file__).resolve().parent / 'static'
COOKIE = 'fitlab_session'
PUBLIC_API = {'/api/health', '/api/auth/register', '/api/auth/login'}
hasher = PasswordHasher()
# Verify a real hash even for unknown usernames to avoid a fast missing-user path.
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r'^[A-Za-z0-9_.-]+$')
    password: str = Field(min_length=8, max_length=200)


def create_app(database_path=None, secure_cookies=None):
    path = str(database_path or os.environ.get('FITLAB_DB_PATH', './fitlab.db'))
    secure = (os.environ.get('FITLAB_SECURE_COOKIES', '').lower() == 'true'
              if secure_cookies is None else secure_cookies)

    @asynccontextmanager
    async def lifespan(app):
        await run_in_threadpool(db.init_db, path)
        yield

    app = FastAPI(title='FitLab', version='0.1.0', lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url='/api/openapi.json')

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

    # Keep unimplemented APIs separate from the static mount and honest about status.
    @app.api_route('/api/{remaining:path}', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
    def unavailable(remaining: str):
        raise HTTPException(501, 'This backend feature is not available yet.')

    app.mount('/', StaticFiles(directory=STATIC_DIR, html=True), name='static')
    return app


app = create_app()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '8000')))
