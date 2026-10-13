"""Priority-column persistence — باگ content_hash=NULL و رگرسیون مسیر معتبر.

فقط sqlite حافظه‌ای؛ بدون تماس با DB واقعی.
"""
from __future__ import annotations

import logging

from backend.database.base import Base
from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news.fetchers import RawItem
from source_bot.output import deliver


def _mem_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _src(db, name="p"):
    s = Source(name=name, collection_method="rss", type="rss",
               feed_url="https://example.test/rss")
    db.add(s)
    db.commit()
    return s


KW = dict(priority="P2", score=62.0, reason="r", priority_source="rules",
          priority_status="RULES_ONLY", duplicate_status="new")


def test_empty_content_null_hash_gets_columns():
    """بازتولید #1020: محتوای تهی -> ستون‌ها روی همان ردیف می‌نشینند."""
    db = _mem_db()
    s = _src(db)
    assert deliver(db, s, RawItem(title=None, url="https://example.test/cbi",
                                  raw_text=None), **KW) is True
    docs = db.query(Document).all()
    assert len(docs) == 1
    d = docs[0]
    assert d.content_hash is None
    assert d.ingestion_priority == "P2"
    assert d.priority_score == 62.0
    assert d.priority_status == "RULES_ONLY"
    assert d.duplicate_status == "new"
    arts = db.query(Article).filter(Article.document_id == d.id).all()
    assert len(arts) == 1 and arts[0].importance is None
    db.close()


def test_valid_content_unchanged_path():
    db = _mem_db()
    s = _src(db)
    assert deliver(db, s, RawItem(title="Real story", url="https://example.test/r",
                                  raw_text="substantive body text here"),
                   **KW) is True
    d = db.query(Document).one()
    assert d.content_hash is not None
    assert (d.ingestion_priority, d.priority_score) == ("P2", 62.0)
    db.close()


def test_duplicate_does_not_touch_columns():
    db = _mem_db()
    s = _src(db)
    item = dict(title="Dup", url="https://example.test/d", raw_text="same body")
    assert deliver(db, s, RawItem(**item), **KW) is True
    other = dict(KW)
    other.update(priority="P0", score=99.0)
    assert deliver(db, s, RawItem(**item), **other) is False
    d = db.query(Document).one()
    assert (d.ingestion_priority, d.priority_score) == ("P2", 62.0)
    db.close()


def test_ambiguous_same_url_rows_never_mistagged(caplog):
    """حالت CBI: یک URL، دو محتوای متفاوت (هر دو نزدیک‌تهی).
    هر ردیف فقط تگ خودش را می‌گیرد؛ ردیف اول دست‌نخورده می‌ماند."""
    db = _mem_db()
    s = _src(db)
    url = "https://example.test/amb"
    assert deliver(db, s, RawItem(title=None, url=url, raw_text="<p>alpha</p>"),
                   **KW) is True
    p0 = dict(KW)
    p0.update(priority="P0", score=95.0)
    assert deliver(db, s, RawItem(title=None, url=url, raw_text="<div>beta</div>"),
                   **p0) is True
    rows = db.query(Document).order_by(Document.retrieved_at).all()
    assert len(rows) == 2  # حقیقت pipeline: هر دو حفظ شده‌اند
    assert (rows[0].ingestion_priority, rows[0].priority_score) == ("P2", 62.0)
    assert (rows[1].ingestion_priority, rows[1].priority_score) == ("P0", 95.0)
    assert "not unique" not in "".join(r.message for r in caplog.records)
    db.close()


def test_ambiguous_guard_returns_none_on_race():
    """نگهبان ابهام: دو کاندید NULL هم‌URL پس از before -> None (نه حدس)."""
    from datetime import UTC, datetime

    from source_bot.output import _find_created_row

    db = _mem_db()
    s = _src(db)
    url = "https://example.test/race"
    before = datetime.now(UTC)
    for _ in range(2):  # شبیه‌سازی race: دو ردیف تهی هم‌زمان
        db.add(Document(source_id=s.id, url=url, title=None, raw_text=None,
                        content_hash=None, retrieved_at=datetime.now(UTC)))
    db.flush()
    doc, status = _find_created_row(db, s, RawItem(title=None, url=url, raw_text=None),
                                    before)
    assert doc is None and status == "ambiguous"
    db.close()


def test_column_failure_keeps_stored_row(caplog):
    """شکست ستون‌گذاری، ردیف ذخیره‌شده را از بین نمی‌برد (rollback جزئی نداریم)."""
    db = _mem_db()
    s = _src(db)
    import source_bot.output as out_module

    real_find = out_module._find_created_row

    def _boom(*a, **k):
        raise RuntimeError("simulated lookup failure")

    out_module._find_created_row = _boom
    try:
        with caplog.at_level(logging.WARNING, logger="source_bot.output"):
            assert deliver(db, s, RawItem(title="Kept", url="https://example.test/k",
                                          raw_text="persistent body"),
                           **KW) is True
        assert any("priority columns skipped" in r.message for r in caplog.records)
    finally:
        out_module._find_created_row = real_find
    d = db.query(Document).one()  # ردیف سر جایش است
    assert d.title == "Kept" and d.ingestion_priority is None
    db.close()


def test_no_url_no_content_skipped_with_clear_warning(caplog):
    """آیتم بدون URL و محتوا: کلیدی برای یافتن نیست؛ warning صریح no_key،
    ردیف ذخیره می‌ماند و Article دست‌نخورده است."""
    db = _mem_db()
    s = _src(db)
    with caplog.at_level(logging.WARNING, logger="source_bot.output"):
        assert deliver(db, s, RawItem(title=None, url=None, raw_text=None),
                       **KW) is True
    assert any("no_key" in r.message for r in caplog.records)
    d = db.query(Document).one()
    assert d.ingestion_priority is None
    arts = db.query(Article).filter(Article.document_id == d.id).all()
    assert len(arts) == 1 and arts[0].importance is None
    db.close()


def test_failed_priority_update_keeps_session_usable(caplog):
    """شکست ستون‌گذاری در آیتم اول، session را برای آیتم بعدی مسموم نمی‌کند."""
    db = _mem_db()
    s = _src(db)
    import source_bot.output as out_module

    real_find = out_module._find_created_row
    calls = {"n": 0}

    def _flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("simulated transient failure")
        return real_find(*a, **k)

    out_module._find_created_row = _flaky
    try:
        with caplog.at_level(logging.WARNING, logger="source_bot.output"):
            assert deliver(db, s, RawItem(title="First", url="https://example.test/1",
                                          raw_text="first body text"),
                           **KW) is True
        # آیتم دوم روی همان session باید کامل موفق شود (ستون‌ها نشسته باشند)
        p0 = dict(KW)
        p0.update(priority="P1", score=80.0)
        assert deliver(db, s, RawItem(title="Second", url="https://example.test/2",
                                      raw_text="second body text"),
                       **p0) is True
    finally:
        out_module._find_created_row = real_find
    rows = {d.title: d for d in db.query(Document).all()}
    assert rows["First"].ingestion_priority is None  # ستون جا ماند، ردیف ماند
    assert (rows["Second"].ingestion_priority, rows["Second"].priority_score) == ("P1", 80.0)
    db.close()
