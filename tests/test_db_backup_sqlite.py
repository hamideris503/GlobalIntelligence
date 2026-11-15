"""SQLite backup/restore/verify — اجرای محلی Windows بدون Docker/pg_dump."""
from __future__ import annotations

import sqlite3

from scripts.db_backup import (
    _sqlite_backup_filename,
    cmd_sqlite_backup,
    cmd_sqlite_restore,
    sqlite_integrity_ok,
    sqlite_path_from_url,
    verify_manifest,
)


def _make_db(path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE sources (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        conn.execute("CREATE TABLE articles (id INTEGER PRIMARY KEY, title TEXT)")
        conn.executemany(
            "INSERT INTO sources (name) VALUES (?)", [("a",), ("b",), ("c",)]
        )
        conn.execute("INSERT INTO articles (title) VALUES ('t1')")
        conn.commit()
    finally:
        conn.close()


def test_sqlite_path_from_url() -> None:
    assert sqlite_path_from_url("sqlite:///./dev.db").name == "dev.db"
    assert sqlite_path_from_url("postgresql+psycopg://u@h/db") is None


def test_sqlite_backup_writes_manifest_and_is_readable(tmp_path) -> None:
    db_path = tmp_path / "live.db"
    _make_db(db_path)
    backup_dir = tmp_path / "backups"

    assert cmd_sqlite_backup(db_path, backup_dir, keep=7) == 0

    files = sorted(backup_dir.glob("gi_backup-*.sqlite3"))
    assert len(files) == 1
    assert verify_manifest(files[0]) is True
    assert sqlite_integrity_ok(files[0]) is True

    # داده‌ها واقعاً در نسخهٔ پشتیبان هستند
    conn = sqlite3.connect(files[0])
    try:
        assert conn.execute("SELECT count(*) FROM sources").fetchone()[0] == 3
    finally:
        conn.close()


def test_sqlite_restore_requires_yes_and_roundtrips(tmp_path) -> None:
    db_path = tmp_path / "live.db"
    _make_db(db_path)
    backup_dir = tmp_path / "backups"
    assert cmd_sqlite_backup(db_path, backup_dir, keep=7) == 0
    archive = sorted(backup_dir.glob("gi_backup-*.sqlite3"))[0]

    target = tmp_path / "restored"
    assert cmd_sqlite_restore(archive, str(target), yes=False) == 1
    assert not target.with_suffix(".sqlite3").exists()

    assert cmd_sqlite_restore(archive, str(target), yes=True) == 0
    restored = target.with_suffix(".sqlite3")
    assert sqlite_integrity_ok(restored) is True
    conn = sqlite3.connect(restored)
    try:
        assert conn.execute("SELECT count(*) FROM articles").fetchone()[0] == 1
    finally:
        conn.close()


def test_sqlite_restore_refuses_tampered_backup(tmp_path) -> None:
    db_path = tmp_path / "live.db"
    _make_db(db_path)
    backup_dir = tmp_path / "backups"
    assert cmd_sqlite_backup(db_path, backup_dir, keep=7) == 0
    archive = sorted(backup_dir.glob("gi_backup-*.sqlite3"))[0]
    archive.write_bytes(archive.read_bytes() + b"tampered")

    assert cmd_sqlite_restore(archive, str(tmp_path / "t"), yes=True) == 1


def test_rotation_keeps_only_requested_count(tmp_path) -> None:
    db_path = tmp_path / "live.db"
    _make_db(db_path)
    backup_dir = tmp_path / "backups"
    for _ in range(3):
        assert cmd_sqlite_backup(db_path, backup_dir, keep=2) == 0
    assert len(list(backup_dir.glob("gi_backup-*.sqlite3"))) <= 2


def test_backup_filename_format() -> None:
    name = _sqlite_backup_filename()
    assert name.startswith("gi_backup-") and name.endswith(".sqlite3")
