"""Phase 59 — یکتایی محتوای ردیف‌های بدون URL در سطح دیتابیس.

`(source_id, content_hash) WHERE hash IS NULL AND content_hash IS NOT NULL
 AND (external_id IS NULL OR trim(external_id) = '')`

SQLite ایزوله/in-memory و SQLite فایلی موقت؛ بدون شبکه، بدون دیتابیس واقعی.
Migration با subprocess روی فایل موقت اجرا می‌شود (همان الگوی phase7).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news.fetchers import RawItem
from domains.news.ingestion import NewsIngestionPipeline
from tests.conftest import TestingSession

ROOT = Path(__file__).resolve().parents[1]
INDEX_NAME = "uq_documents_source_content_hash_ridless"
PREDICATE = "hash IS NULL AND content_hash IS NOT NULL AND (external_id IS NULL OR trim(external_id) = '')"
PREV_REVISION = "a7c1f5e9b3d2"   # head پیش از این migration (phase7 external_id)
REVISION = "d91e4c7a2b60"        # همین migration
HASH_ONE = "c" * 64
HASH_TWO = "d" * 64


def _src(db, name: str = "c59") -> Source:
    src = Source(name=name, collection_method="dataset", type="api")
    db.add(src)
    db.commit()
    return src


def _ridless(source_id, content_hash: str | None, external_id: str | None = None) -> Document:
    """ردیف بدون URL — بدون عبور از store_item (تست خود قید DB)."""
    return Document(source_id=source_id, external_id=external_id, hash=None,
                    content_hash=content_hash, raw_payload="{}")


# --- ۱: ردیف تکراری بدون URL ممنوع ---
def test_duplicate_ridless_content_identity_is_rejected_by_db() -> None:
    db = TestingSession()
    try:
        src = _src(db)
        db.add(_ridless(src.id, HASH_ONE))
        db.commit()
        db.add(_ridless(src.id, HASH_ONE))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.query(Document).count() == 1
    finally:
        db.close()


# --- ۲ و ۳: کلیدهای متفاوت مجاز ---
def test_other_content_hash_same_source_is_allowed() -> None:
    db = TestingSession()
    try:
        src = _src(db)
        db.add(_ridless(src.id, HASH_ONE))
        db.add(_ridless(src.id, HASH_TWO))
        db.commit()
        assert db.query(Document).count() == 2
    finally:
        db.close()


def test_same_content_hash_in_other_source_is_allowed() -> None:
    db = TestingSession()
    try:
        first, second = _src(db, "c59-a"), _src(db, "c59-b")
        db.add(_ridless(first.id, HASH_ONE))
        db.add(_ridless(second.id, HASH_ONE))
        db.commit()
        assert db.query(Document).count() == 2  # یکتایی فقط درون یک منبع
    finally:
        db.close()


# --- ۴: external_id معتبر قید خودش را دارد ---
def test_valid_external_id_rows_keep_their_own_constraint() -> None:
    db = TestingSession()
    try:
        src = _src(db)
        db.add(_ridless(src.id, HASH_ONE, external_id="cpi:2026-01"))
        db.add(_ridless(src.id, HASH_ONE))  # همان محتوا ولی بدون external_id
        db.commit()
        assert db.query(Document).count() == 2  # ادغام نشدند

        db.add(_ridless(src.id, HASH_TWO, external_id="cpi:2026-01"))
        with pytest.raises(IntegrityError):  # قید اختصاصی external_id دست‌نخورده
            db.commit()
        db.rollback()
        assert db.query(Document).count() == 2
    finally:
        db.close()


# --- ۵: external_id خالی/فاصله‌دار شناسه‌ی معتبر نیست ---
@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_external_id_does_not_escape_the_content_identity(blank: str) -> None:
    db = TestingSession()
    try:
        src = _src(db)
        db.add(_ridless(src.id, HASH_ONE, external_id=blank))
        db.commit()
        db.add(_ridless(src.id, HASH_ONE))
        with pytest.raises(IntegrityError):  # همان محتوا، بدون شناسه‌ی معتبر
            db.commit()
        db.rollback()
        assert db.query(Document).count() == 1
    finally:
        db.close()


# --- ۶: ردیف‌های کاملاً بی‌هویت (content_hash تهی) زیر این index نمی‌آیند ---
def test_identity_less_rows_are_not_merged_by_the_index() -> None:
    db = TestingSession()
    try:
        src = _src(db)
        db.add(_ridless(src.id, None))
        db.add(_ridless(src.id, None))
        db.commit()
        assert db.query(Document).count() == 2
    finally:
        db.close()


# --- ۷: ردیف‌های URL‌دار رفتار قبلی خود را حفظ می‌کنند ---
def test_url_rows_keep_previous_behaviour() -> None:
    db = TestingSession()
    try:
        src = _src(db)
        url = "https://example.test/a"
        db.add(Document(source_id=src.id, url=url, hash="u1", content_hash=HASH_ONE))
        db.add(Document(source_id=src.id, url=url, hash="u1", content_hash=HASH_TWO))
        db.commit()
        assert db.query(Document).count() == 2  # revision: همان URL، محتوای متفاوت

        db.add(Document(source_id=src.id, url=url, hash="u1", content_hash=HASH_ONE))
        with pytest.raises(IntegrityError):  # قید یکتای URL‌دار قبلی
            db.commit()
        db.rollback()
        assert db.query(Document).count() == 2
    finally:
        db.close()


# --- ۸: payload-only از مسیر store_item همچنان idempotent است ---
def test_payload_only_store_item_stays_idempotent() -> None:
    db = TestingSession()
    try:
        src = _src(db)
        pipeline = NewsIngestionPipeline(db)
        item = RawItem(title=None, url=None, raw_text=None,
                       raw_payload='{"metric": "a", "value": 1}')
        assert pipeline.store_item(src, item) is True
        db.commit()
        assert pipeline.store_item(src, item) is False  # نه خطا، نه ردیف دوم
        db.commit()
        assert db.query(Document).count() == 1
        assert db.query(Article).count() == 1
    finally:
        db.close()


# --- ۹: باخت رقابت هم‌زمان = duplicate، بدون Article یتیم و بدون موفقیت کاذب ---
def test_lost_insert_race_reports_duplicate_without_orphan_article(monkeypatch) -> None:
    db = TestingSession()
    try:
        src = _src(db)
        pipeline = NewsIngestionPipeline(db)
        item = RawItem(title=None, url=None, raw_text=None,
                       raw_payload='{"metric": "a", "value": 1}')

        real = NewsIngestionPipeline._identity_exists
        calls = {"n": 0}

        def blind_precheck(self, source, norm):  # noqa: ANN001, ANN202
            calls["n"] += 1
            return False if calls["n"] == 1 else real(self, source, norm)

        assert pipeline.store_item(src, item) is True
        db.commit()
        monkeypatch.setattr(NewsIngestionPipeline, "_identity_exists", blind_precheck)
        assert pipeline.store_item(src, item) is False  # قید DB برنده را رد کرد
        db.commit()
        assert calls["n"] == 1  # پیش‌بررسی کور شد؛ تصمیم از مسیر IntegrityError آمد
        assert db.query(Document).count() == 1
        assert db.query(Article).count() == 1  # Article یتیم از savepoint بیرون نماند
    finally:
        db.close()


# --- ۱۰: DDL برای PostgreSQL بدون اتصال (اجرای واقعی PG اینجا ممکن نیست) ---
def test_model_index_compiles_for_postgres_with_same_predicate() -> None:
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateIndex

    index = next(i for i in Document.__table__.indexes if i.name == INDEX_NAME)
    ddl = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
    assert "CREATE UNIQUE INDEX" in ddl.upper()
    assert "(source_id, content_hash)" in ddl
    assert PREDICATE in ddl


# =====================================================================
# Migration (SQLite فایلی موقت) — PostgreSQL اینجا اجرا نشد
# =====================================================================
def _throwaway_schema(db_path: Path):
    """اسکیمای create_all در وضعیت پیش از این migration.

    create_all از metadata امروز استفاده می‌کند، پس جدول‌هایی که migrationهای
    بعدیِ این تست ساخته‌اند باید حذف شوند تا replay از PREV واقعی باشد
    (Stage89: article_dispatches).
    """
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS article_dispatches"))
        conn.execute(text(f"DROP INDEX {INDEX_NAME}"))
    return engine


def _alembic(db_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path.as_posix()}"}
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT,
                          env=env, capture_output=True, text=True)


def _index_sql(db_path: Path) -> str | None:
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='index' AND name=:n"),
                {"n": INDEX_NAME},
            ).scalar()
    finally:
        engine.dispose()


def _version(db_path: Path) -> str | None:
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    try:
        with engine.connect() as conn:
            return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    finally:
        engine.dispose()


def _rows(db_path: Path) -> int:
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    try:
        with engine.connect() as conn:
            return conn.execute(text("SELECT COUNT(*) FROM documents")).scalar()
    finally:
        engine.dispose()


def test_migration_adds_and_drops_the_index(tmp_path) -> None:
    db_path = tmp_path / "mig59.sqlite3"
    engine = _throwaway_schema(db_path)
    engine.dispose()
    assert _index_sql(db_path) is None

    assert _alembic(db_path, "stamp", PREV_REVISION).returncode == 0
    # Upgrade exactly to this migration's revision (head may move on later
    # stages); the test is about phase59, not whatever is current head.
    proc = _alembic(db_path, "upgrade", REVISION)
    assert proc.returncode == 0, proc.stderr[-800:]
    assert _version(db_path) == REVISION
    assert PREDICATE in (_index_sql(db_path) or "")

    assert _alembic(db_path, "downgrade", "-1").returncode == 0
    assert _index_sql(db_path) is None
    assert _version(db_path) == PREV_REVISION

    assert _alembic(db_path, "upgrade", "head").returncode == 0


def test_migration_stops_on_existing_duplicates_without_touching_data(tmp_path) -> None:
    """duplicate موجود: Migration پیش از ساخت index متوقف می‌شود و داده دست‌نخورده."""
    db_path = tmp_path / "dup59.sqlite3"
    engine = _throwaway_schema(db_path)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        first = Source(name="dup59-a", collection_method="dataset", type="api")
        second = Source(name="dup59-b", collection_method="dataset", type="api")
        db.add_all([first, second])
        db.commit()
        for src, chash in ((first, HASH_ONE), (second, HASH_TWO)):
            db.add(_ridless(src.id, chash))
            db.add(_ridless(src.id, chash))
        db.commit()
    engine.dispose()

    assert _alembic(db_path, "stamp", PREV_REVISION).returncode == 0
    proc = _alembic(db_path, "upgrade", "head")
    output = proc.stdout + proc.stderr
    assert proc.returncode != 0
    assert "duplicate" in output and "2 duplicate" in output
    assert HASH_ONE[:12] in output  # شناسه‌ی نمونه، بدون محتوای خام
    assert _version(db_path) == PREV_REVISION  # نسخه تغییر نکرد
    assert _rows(db_path) == 4                 # هیچ ردیفی حذف/ادغام نشد
    assert _index_sql(db_path) is None         # index ساخته نشد
