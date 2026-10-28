"""Phase 7 — هویت ردیف بدون URL: index یکتای جزئی، هم‌زمانی، و Migration.

ردیف‌های بدون URL (سری زمانی CSV) با (source_id, external_id) یکی می‌شوند؛
ردیف‌های URL‌دار، revision و dedup قبلی دست‌نخورده می‌مانند. هیچ داده‌ای
به‌صورت خودکار حذف/ادغام نمی‌شود و Migration روی SQLite دورانداختنی اجرا می‌شود.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.models.document import Document
from backend.database.models.source import Source
from tests.conftest import TestingSession
from tests.test_source_bot_phase6 import _file_db, _series_item, _series_source

ROOT = Path(__file__).resolve().parents[1]
INDEX_NAME = "uq_documents_source_external_id"
PREDICATE = "external_id IS NOT NULL AND hash IS NULL"
PREV_REVISION = "c41d9e2b7f3a"
REVISION = "a7c1f5e9b3d2"


def _pipeline(db):  # noqa: ANN001, ANN202
    from domains.news.ingestion import NewsIngestionPipeline

    return NewsIngestionPipeline(db)


def _url_item(url: str, text_body: str):
    from domains.news.fetchers import RawItem

    return RawItem(title="URL doc", url=url, raw_text=text_body,
                   metadata={"adapter": "html"})


# =====================================================================
# بخش ۱ — index جزئی روی همین اسکیمای مشترک
# =====================================================================
def _index_sql(engine) -> str | None:  # noqa: ANN001
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name=:n"
        ), {"n": INDEX_NAME}).scalar()
    return row


def test_partial_unique_index_is_declared_and_enforced():
    from tests.conftest import engine

    sql = _index_sql(engine) or ""
    assert "CREATE UNIQUE INDEX" in sql.upper()
    assert PREDICATE in sql

    src = _series_source(TestingSession(), "idx-src")
    db = TestingSession()
    db.add(Document(source_id=src.id, external_id="cpi:2026-01", hash=None,
                    content_hash=None, raw_payload="{}"))
    db.commit()
    db.add(Document(source_id=src.id, external_id="cpi:2026-01", hash=None,
                    content_hash=None, raw_payload="{}"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # ردیف URL‌دار (hash دار) بیرون از predicate است: قید هویتی او را نمی‌گیرد
    db.add(Document(source_id=src.id, external_id="cpi:2026-01", hash="h1",
                    content_hash="c1", raw_payload="{}"))
    db.add(Document(source_id=src.id, external_id="cpi:2026-01", hash="h2",
                    content_hash="c2", raw_payload="{}"))
    db.commit()
    assert db.query(Document).filter(Document.hash.isnot(None)).count() == 2


def test_sequential_repeat_of_one_period_is_duplicate(tmp_path):
    Session = _file_db(tmp_path)
    with Session() as db:
        src = _series_source(db, "series-seq7")
        pipeline = _pipeline(db)
        assert pipeline.store_item(src, _series_item("cpi:2026-01")) is True
        db.commit()
        assert pipeline.store_item(src, _series_item("cpi:2026-01")) is False
        db.commit()
        assert db.query(Document).count() == 1


def test_two_periods_of_one_indicator_are_both_stored(tmp_path):
    Session = _file_db(tmp_path)
    with Session() as db:
        src = _series_source(db, "series-two7")
        pipeline = _pipeline(db)
        assert pipeline.store_item(src, _series_item("cpi:2026-01")) is True
        assert pipeline.store_item(src, _series_item("cpi:2026-02")) is True
        db.commit()
        ids = db.execute(select(Document.external_id)).scalars().all()
        assert sorted(ids) == ["cpi:2026-01", "cpi:2026-02"]


def test_concurrent_same_identity_creates_exactly_one_row(tmp_path):
    """دو درج واقعاً هم‌زمان (دو اتصال + barrier در نقطه‌ی TOCTOU) ⇒ یک ردیف.

    برنده نتیجه‌ی True و بازنده (نقض index) نتیجه‌ی False می‌گیرد؛ هیچ خطایی
    بیرون نمی‌زند و هر دو نتیجه با قرارداد duplicate سازگار است.
    """
    Session = _file_db(tmp_path)
    with Session() as db:
        src = _series_source(db, "series-race7")
        src_id = src.id

    barrier = threading.Barrier(2, timeout=30)
    results: list[bool] = []
    errors: list[BaseException] = []

    def worker() -> None:
        db = Session()
        try:
            pipeline = _pipeline(db)
            real_execute = db.execute
            state = {"first": True}

            def execute(*a, **k):  # noqa: ANN002, ANN003
                out = real_execute(*a, **k)
                if state["first"]:      # بررسی وجود انجام شد؛ پیش از درج توقف کن
                    state["first"] = False
                    barrier.wait()
                return out

            db.execute = execute
            results.append(pipeline.store_item(src, _series_item("cpi:2026-02")))
            db.commit()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
            db.rollback()
        finally:
            db.close()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=40)

    assert errors == []
    assert sorted(results) == [False, True]      # یکی ذخیره، دیگری duplicate
    with Session() as db:
        count = db.execute(
            select(func.count()).select_from(Document).where(Document.source_id == src_id)
        ).scalar_one()
    assert count == 1


def test_session_stays_usable_after_a_lost_duplicate(tmp_path):
    """savepoint: درج تکراری فقط خودش برمی‌گردد؛ درج بعدی سالم ذخیره می‌شود."""
    Session = _file_db(tmp_path)
    with Session() as db:
        src = _series_source(db, "series-savepoint7")
        pipeline = _pipeline(db)
        assert pipeline.store_item(src, _series_item("cpi:2026-01")) is True
        assert pipeline.store_item(src, _series_item("cpi:2026-01")) is False
        assert pipeline.store_item(src, _series_item("cpi:2026-03")) is True
        db.commit()
        assert db.query(Document).count() == 2


def test_other_db_error_is_not_reported_as_duplicate(tmp_path):
    """خطای DB غیر از نقض هویت باید بالا برود (نه duplicate پنهان).

    روی DB دورانداختنی یک قید یکتای *دیگر* (raw_text) ساخته می‌شود؛ پس درج
    دوم IntegrityError واقعی و غیرهویتی می‌دهد و دروازه‌ی duplicate نباید آن را
    ببلعد (external_id دوم هیچ ردیفی ندارد).
    """
    Session = _file_db(tmp_path)
    with Session() as db:
        src = _series_source(db, "series-other-error")
        pipeline = _pipeline(db)
        assert pipeline.store_item(src, _series_item("cpi:2026-01")) is True
        db.commit()
        db.execute(text("CREATE UNIQUE INDEX tmp_uq_raw_text ON documents (raw_text)"))
        db.commit()
        with pytest.raises(IntegrityError):
            pipeline.store_item(src, _series_item("cpi:2026-02"))
        db.rollback()
    with Session() as db:
        assert db.query(Document).count() == 1


def test_url_documents_keep_hash_dedup_and_revision(tmp_path):
    Session = _file_db(tmp_path)
    with Session() as db:
        src = _series_source(db, "url-dedup7")
        pipeline = _pipeline(db)
        url = "https://example.test/article"
        assert pipeline.store_item(src, _url_item(url, "body one")) is True
        db.commit()
        assert pipeline.store_item(src, _url_item(url, "body one")) is False   # dedup قبلی
        db.commit()
        assert pipeline.store_item(src, _url_item(url, "body two")) is True    # revision
        db.commit()
        revisions = db.execute(
            select(Document.revision).order_by(Document.revision)
        ).scalars().all()
        assert revisions == [1, 2]
        assert db.query(Document).count() == 2


# =====================================================================
# بخش ۲ — Migration روی SQLite دورانداختنی (PostgreSQL اینجا اجرا نشد)
# =====================================================================
def _throwaway_schema(db_path: Path):
    """اسکیمای head-۱ + index حذف‌شده: وضعیت واقعی پیش از این Migration."""
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text(f"DROP INDEX {INDEX_NAME}"))
    return engine


def _alembic(db_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path.as_posix()}"}
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT,
                          env=env, capture_output=True, text=True)


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


def test_migration_adds_and_drops_the_index(tmp_path):
    db_path = tmp_path / "mig7.sqlite3"
    engine = _throwaway_schema(db_path)
    assert _index_sql(engine) is None
    engine.dispose()

    assert _alembic(db_path, "stamp", PREV_REVISION).returncode == 0
    proc = _alembic(db_path, "upgrade", REVISION)  # صریح: head در فازهای بعد جابه‌جا می‌شود
    assert proc.returncode == 0, proc.stderr[-800:]
    assert _version(db_path) == REVISION

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    assert PREDICATE in (_index_sql(engine) or "")
    engine.dispose()

    assert _alembic(db_path, "downgrade", "-1").returncode == 0
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    assert _index_sql(engine) is None
    engine.dispose()
    assert _version(db_path) == PREV_REVISION

    assert _alembic(db_path, "upgrade", REVISION).returncode == 0


def test_migration_stops_on_existing_duplicates_without_touching_data(tmp_path):
    """duplicate موجود: Migration پیش از ساخت index متوقف می‌شود و داده دست‌نخورده."""
    db_path = tmp_path / "dup7.sqlite3"
    engine = _throwaway_schema(db_path)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as db:
        src = Source(name="dup-src", collection_method="dataset", type="api")
        db.add(src)
        db.commit()
        for _ in range(2):
            db.add(Document(source_id=src.id, external_id="cpi:2026-01", hash=None,
                            content_hash=None, raw_payload="{}"))
        db.commit()
    engine.dispose()

    assert _alembic(db_path, "stamp", PREV_REVISION).returncode == 0
    proc = _alembic(db_path, "upgrade", "head")
    output = proc.stdout + proc.stderr
    assert proc.returncode != 0
    assert "duplicate" in output and "cpi:2026-01" in output
    assert _version(db_path) == PREV_REVISION      # نسخه تغییر نکرد
    assert _rows(db_path) == 2                     # هیچ ردیفی حذف/ادغام نشد

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    assert _index_sql(engine) is None              # index ساخته نشد
    engine.dispose()
