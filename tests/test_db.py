from pathlib import Path
import sqlite3
import pytest
import db


def test_initialization_is_idempotent_and_cascades(tmp_path):
    path = tmp_path / 'test.db'
    db.init_db(path)
    user = db.create_user(path, 'alice', 'hashed')
    db.create_session(path, user['id'], 'opaque')
    db.init_db(path)
    assert db.get_user_by_name(path, 'ALICE')['id'] == user['id']
    with db.connection(path) as conn:
        assert conn.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
        assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        conn.execute('DELETE FROM users WHERE id=?', (user['id'],))
    assert db.get_session_user(path, 'opaque') is None


def test_job_writes_are_owner_scoped_and_admission_is_bounded(tmp_path):
    path = tmp_path / 'test.db'
    db.init_db(path)
    alice = db.create_user(path, 'alice', 'hashed')['id']
    bob = db.create_user(path, 'bob', 'hashed')['id']
    job = db.create_job(path, alice, 'generate', {})
    db.update_job(path, bob, job, 'failed')
    assert db.get_job(path, bob, job) is None
    assert db.get_job(path, alice, job)['status'] == 'queued'
    db.create_job(path, alice, 'generate', {})
    with pytest.raises(ValueError):
        db.create_job(path, alice, 'generate', {})
    db.recover_jobs(path)
    assert db.get_job(path, alice, job)['status'] == 'failed'
    assert db.create_job(path, alice, 'generate', {})


def test_failed_transaction_rolls_back(tmp_path):
    path = tmp_path / 'test.db'
    db.init_db(path)
    with pytest.raises(sqlite3.IntegrityError):
        with db.connection(path) as conn:
            conn.execute("INSERT INTO users(username,password_hash) VALUES ('alice','hash')")
            conn.execute("INSERT INTO users(username,password_hash) VALUES ('ALICE','hash')")
    assert db.get_user_by_name(path, 'alice') is None


def test_save_rejects_another_users_source_job(tmp_path):
    path = tmp_path / 'test.db'
    db.init_db(path)
    alice = db.create_user(path, 'alice', 'hashed')['id']
    bob = db.create_user(path, 'bob', 'hashed')['id']
    job_id = db.create_job(path, alice, 'generate', {})
    job = db.get_job(path, alice, job_id)
    with pytest.raises(ValueError):
        db.save_look(path, bob, job, {'critique': {}})
