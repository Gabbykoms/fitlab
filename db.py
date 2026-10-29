"""SQLite persistence with ownership-scoped styling queries."""
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

    init_styling(path)


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


# Styling persistence. Paths are private; API serializers load image bytes only
# after the caller has passed an ownership-filtered lookup.
import json
import secrets


def init_styling(path):
    with connection(path) as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS wardrobe_items (
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            category TEXT NOT NULL, label TEXT, filename TEXT NOT NULL, mime TEXT NOT NULL,
            byte_size INTEGER NOT NULL, width INTEGER, height INTEGER, sha256 TEXT NOT NULL,
            upload_path TEXT NOT NULL, preflight_json TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(user_id, sha256));
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            kind TEXT NOT NULL, status TEXT NOT NULL, brief_json TEXT NOT NULL, weather_json TEXT,
            options_json TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS looks (
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            job_id TEXT, option_index INTEGER NOT NULL, title TEXT, occasion TEXT, event_date TEXT,
            image_path TEXT NOT NULL, pieces_json TEXT NOT NULL, brief_json TEXT NOT NULL,
            critique_json TEXT NOT NULL, weather_json TEXT, unresolved_json TEXT NOT NULL,
            overall_score INTEGER, retry_recommended INTEGER, created_at TEXT NOT NULL,
            provenance_json TEXT NOT NULL, option_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS wardrobe_user ON wardrobe_items(user_id);
        CREATE INDEX IF NOT EXISTS jobs_user ON jobs(user_id, created_at);
        CREATE INDEX IF NOT EXISTS looks_user ON looks(user_id, created_at);
        CREATE INDEX IF NOT EXISTS looks_occasion ON looks(user_id, occasion);
        ''')


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def add_wardrobe_item(path, user_id, category, label, image_path, metadata, byte_size, digest, preflight):
    with connection(path) as conn:
        cursor = conn.execute('''INSERT INTO wardrobe_items
            (user_id,category,label,filename,mime,byte_size,width,height,sha256,upload_path,preflight_json,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', (user_id, category, label, Path(image_path).name,
            metadata['mime'], byte_size, metadata['width'], metadata['height'], digest, image_path,
            json.dumps(preflight), now_iso()))
        return dict(conn.execute('SELECT * FROM wardrobe_items WHERE user_id=? AND id=?',
                                 (user_id, cursor.lastrowid)).fetchone())


def list_wardrobe_items(path, user_id):
    with connection(path) as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM wardrobe_items WHERE user_id=? ORDER BY id', (user_id,))]


def get_wardrobe_item(path, user_id, item_id):
    with connection(path) as conn:
        row = conn.execute('SELECT * FROM wardrobe_items WHERE user_id=? AND id=?', (user_id, item_id)).fetchone()
        return dict(row) if row else None


def duplicate_upload(path, user_id, digest):
    with connection(path) as conn:
        return conn.execute('SELECT id FROM wardrobe_items WHERE user_id=? AND sha256=?', (user_id, digest)).fetchone() is not None


def delete_wardrobe_item(path, user_id, item_id):
    with connection(path) as conn:
        return bool(conn.execute('DELETE FROM wardrobe_items WHERE user_id=? AND id=?', (user_id, item_id)).rowcount)


def create_job(path, user_id, kind, brief, weather=None):
    job_id, now = secrets.token_hex(16), now_iso()
    with connection(path) as conn:
        # SQLite serializes admission checks with the insert, including double submits.
        conn.execute('BEGIN IMMEDIATE')
        active = conn.execute("SELECT count(*) FROM jobs WHERE user_id=? AND status IN ('queued','running')", (user_id,)).fetchone()[0]
        if active >= 2:
            raise ValueError('Two styling jobs are already running. Please wait for one to finish.')
        conn.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)',
                     (job_id, user_id, kind, 'queued', json.dumps(brief), json.dumps(weather), '[]', None, now, now))
    return job_id


def get_job(path, user_id, job_id):
    with connection(path) as conn:
        row = conn.execute('SELECT * FROM jobs WHERE user_id=? AND id=?', (user_id, job_id)).fetchone()
    if row is None:
        return None
    result = dict(row)
    for key in ('brief', 'weather', 'options'):
        result[key] = json.loads(result.pop(key + '_json'))
    return result


def update_job(path, user_id, job_id, status, options=None, weather=None, error=None):
    with connection(path) as conn:
        conn.execute('''UPDATE jobs SET status=?,options_json=COALESCE(?,options_json),
            weather_json=COALESCE(?,weather_json),error=?,updated_at=? WHERE user_id=? AND id=?''',
            (status, json.dumps(options) if options is not None else None,
             json.dumps(weather) if weather is not None else None, error, now_iso(), user_id, job_id))


def recover_jobs(path):
    with connection(path) as conn:
        conn.execute("UPDATE jobs SET status='failed',error=?,updated_at=? WHERE status IN ('queued','running')",
                     ('The server restarted before this request finished. Please try again.', now_iso()))


def save_look(path, user_id, job, option):
    brief, critique = job['brief'], option['critique']
    with connection(path) as conn:
        owned = conn.execute('SELECT id FROM jobs WHERE user_id=? AND id=?', (user_id, job['id'])).fetchone()
        if owned is None:
            raise ValueError('That look is no longer available.')
        cursor = conn.execute('''INSERT INTO looks (user_id,job_id,option_index,occasion,event_date,
            image_path,pieces_json,brief_json,critique_json,weather_json,unresolved_json,
            overall_score,retry_recommended,created_at,provenance_json,option_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (user_id, job['id'], option['index'], brief['occasion'], brief['event_date'], option['image_path'],
             json.dumps(option['pieces']), json.dumps(brief), json.dumps(critique), json.dumps(job['weather']),
             json.dumps(option['unresolved']), critique.get('overall'), critique.get('retry_recommended'),
             now_iso(), json.dumps(option['provenance']), json.dumps(option)))
        return cursor.lastrowid


def list_looks(path, user_id, occasion=None, from_date=None, to_date=None):
    query = 'SELECT * FROM looks WHERE user_id=?'
    params = [user_id]
    if occasion:
        query += ' AND instr(lower(occasion),lower(?)) > 0'
        params.append(occasion)
    if from_date:
        query += ' AND event_date >= ?'
        params.append(str(from_date))
    if to_date:
        query += ' AND event_date <= ?'
        params.append(str(to_date))
    with connection(path) as conn:
        return [dict(r) for r in conn.execute(query + ' ORDER BY id DESC', params)]


def delete_look(path, user_id, look_id):
    with connection(path) as conn:
        return bool(conn.execute('DELETE FROM looks WHERE user_id=? AND id=?', (user_id, look_id)).rowcount)
