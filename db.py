"""SQLite persistence for the initial accounts/session backend slice."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

SESSION_SECONDS = 30 * 86400


@contextmanager
def connection(path):
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA foreign_keys = ON')
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connection(path) as conn:
        conn.execute('PRAGMA journal_mode = WAL')
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
        ''')


def healthy(path):
    # Do not create a replacement database when the configured file disappears.
    if not Path(path).is_file():
        return False
    try:
        with connection(path) as conn:
            conn.execute('SELECT id FROM users LIMIT 1').fetchone()
        return True
    except sqlite3.Error:
        return False


def create_user(path, username, password_hash):
    with connection(path) as conn:
        cursor = conn.execute('INSERT INTO users(username, password_hash) VALUES (?, ?)',
                              (username, password_hash))
        return dict(conn.execute('SELECT * FROM users WHERE id = ?', (cursor.lastrowid,)).fetchone())


def get_user_by_name(path, username):
    with connection(path) as conn:
        row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        return dict(row) if row else None


def create_session(path, user_id, token, previous_token=None):
    now = datetime.now(timezone.utc)
    with connection(path) as conn:
        if previous_token:
            conn.execute('DELETE FROM sessions WHERE token = ? AND user_id = ?',
                         (previous_token, user_id))
        conn.execute('INSERT INTO sessions VALUES (?, ?, ?, ?)',
                     (token, user_id, now.isoformat(),
                      (now + timedelta(seconds=SESSION_SECONDS)).isoformat()))


def get_session_user(path, token):
    now = datetime.now(timezone.utc)
    with connection(path) as conn:
        row = conn.execute('''SELECT users.id AS user_id, users.username, sessions.expires_at
                              FROM sessions JOIN users ON users.id = sessions.user_id
                              WHERE sessions.token = ?''', (token,)).fetchone()
        if not row:
            return None
        if datetime.fromisoformat(row['expires_at']) <= now:
            conn.execute('DELETE FROM sessions WHERE token = ?', (token,))
            return None
        conn.execute('UPDATE sessions SET expires_at = ? WHERE token = ?',
                     ((now + timedelta(seconds=SESSION_SECONDS)).isoformat(), token))
        return {'user_id': row['user_id'], 'username': row['username']}


def delete_session(path, token):
    with connection(path) as conn:
        conn.execute('DELETE FROM sessions WHERE token = ?', (token,))
