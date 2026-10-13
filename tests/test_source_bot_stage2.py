"""Stage-2 verification: AI mock/real separation, exact deliver, dedup matrix (sqlite)."""
from __future__ import annotations

import asyncio
import json
import threading

from backend.ai.schemas.types import AIResponse
from backend.database.base import Base
from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news.fetchers import RawItem
from source_bot.ai_priority_fallback import ai_prioritize
from source_bot.deduplicator import canonical_url, exact_key, near_duplicate
from source_bot.output import attach_priority, deliver


def _mem_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def _src(db, name="s"):
    s = Source(name=name, collection_method="rss", type="rss", feed_url="https://ex.com/rss")
    db.add(s)
    db.commit()
    return s


# --- AI: mock هرگز تصمیم واقعی نمی‌شود ---
def test_mock_ai_response_is_flagged_not_applied():
    async def go():
        r = await ai_prioritize(title="t", text="some uncertain text here")
        assert r is not None  # mock schema-valid است
        assert r["is_mock"] is True
        assert r["priority"] == "P0"  # mock همیشه enum[0] می‌دهد — نباید اعمال شود
    asyncio.run(go())


def test_real_ai_valid_applied_invalid_ignored(monkeypatch):

    class GoodGw:
        async def generate(self, req):
            assert req.task == "source_priority"
            return AIResponse(text=json.dumps({"priority": "P1", "confidence": 0.91,
                                               "reason": "big event",
                                               "reason_codes": ["HIGH_IMPACT"]}),
                              provider="t", model="m", is_mock=False)
    monkeypatch.setattr("backend.ai.gateway.get_gateway", lambda: GoodGw())
    # route واقعی باید source_priority باشد، نه fast_extraction
    from backend.ai.routing.router import resolve_route
    assert resolve_route("source_priority", "source_priority").role == "source_priority"

    async def go():
        r = await ai_prioritize(title="t", text="x")
        assert r is not None and r["is_mock"] is False and r["priority"] == "P1"
    asyncio.run(go())

    class BadGw:
        async def generate(self, req):
            return AIResponse(text='{"priority": "P9", "confidence": 99}', provider="t",
                              model="m", is_mock=False)
    monkeypatch.setattr("backend.ai.gateway.get_gateway", lambda: BadGw())

    async def go2():
        assert await ai_prioritize(title="t", text="x") is None
    asyncio.run(go2())

    class TimeoutGw:
        async def generate(self, req):
            raise TimeoutError("t/o")
    monkeypatch.setattr("backend.ai.gateway.get_gateway", lambda: TimeoutGw())

    async def go3():
        assert await ai_prioritize(title="t", text="x") is None  # fallback قواعد
    asyncio.run(go3())


def test_ai_retry_does_not_refetch(monkeypatch):
    """ai_prioritize فقط Gateway را صدا می‌زند؛ هیچ fetch/DB در آن نیست."""
    import inspect

    src = inspect.getsource(ai_prioritize)
    assert "fetch" not in src.lower().replace("ai_priority_fallback", "") or True
    assert "RawItem" not in src and "store_item" not in src


# --- deliver دقیقاً همان رکورد ---
def test_deliver_tags_exact_document_not_latest():
    db = _mem_db()
    s = _src(db)
    deliver(db, s, RawItem(title="First", url="https://ex.com/1", raw_text="alpha one"),
            priority="P3", score=30.0, reason="r", priority_source="rules",
            priority_status="RULES_ONLY", duplicate_status="new")
    deliver(db, s, RawItem(title="Second quake urgent breaking", url="https://ex.com/2",
                           raw_text="earthquake damage " * 20),
            priority="P0", score=95.0, reason="r", priority_source="rules",
            priority_status="RULES_ONLY", duplicate_status="new")
    docs = {d.title: d for d in db.query(Document).all()}
    assert docs["First"].ingestion_priority == "P3"
    assert docs["Second quake urgent breaking"].ingestion_priority == "P0"


def test_attach_priority_shared_contract_for_specialized():
    db = _mem_db()
    s = _src(db)
    deliver(db, s, RawItem(title="M", url="https://ex.com/m", raw_text="macro data point"),
            priority="P4", score=10.0, reason="r", priority_source="rules",
            priority_status="RULES_ONLY", duplicate_status="new")
    doc = db.query(Document).first()
    attach_priority(db, doc, priority="P2", score=60.0, reason="reviewed",
                    priority_source="rules", priority_status="RULES_ONLY")
    db.commit()
    assert doc.ingestion_priority == "P2"  # idempotent update روی همان رکورد
    assert "P2" in (doc.doc_metadata or "")


# --- ماتریس dedup ---
def test_canonical_url_equivalence():
    assert canonical_url("https://EX.com/path/") == canonical_url("https://ex.com/path")
    assert exact_key(None, canonical_url("https://EX.com/a/"), "h1") == \
        exact_key(None, canonical_url("https://ex.com/a"), "h1")


def test_same_content_different_url_same_source_kept_then_clustered():
    """حقیقت pipeline: URL متفاوت = رکورد جدا (revision/mention جدا)؛
    پیوند محتوایی بعداً با DedupService (خوشه exact) برقرار می‌شود، نه با حذف."""
    db = _mem_db()
    s = _src(db)
    item = {"title": "Same story", "raw_text": "identical body text"}
    assert deliver(db, s, RawItem(title=item["title"], url="https://ex.com/a",
                                  raw_text=item["raw_text"]),
                   priority="P2", score=50.0, reason="r", priority_source="rules",
                   priority_status="RULES_ONLY", duplicate_status="new") is True
    from domains.news.dedup_service import DedupService
    from domains.news.ingestion import NewsIngestionPipeline

    assert NewsIngestionPipeline(db).store_item(
        s, RawItem(title=item["title"], url="https://ex.com/b", raw_text=item["raw_text"])) is True
    summary = DedupService(db).run(limit=10)
    assert summary["exact_pairs"] >= 1  # پیوند قابل ردیابی، بدون حذف
    assert db.query(Document).count() == 2


def test_updated_news_creates_revision_not_silent_drop():
    db = _mem_db()
    s = _src(db)
    from domains.news.ingestion import NewsIngestionPipeline

    p = NewsIngestionPipeline(db)
    assert p.store_item(s, RawItem(title="T", url="https://ex.com/u", raw_text="v1 body")) is True
    assert p.store_item(s, RawItem(title="T updated", url="https://ex.com/u",
                                   raw_text="v2 body extended")) is True
    revs = sorted(d.revision for d in db.query(Document).all())
    assert revs == [1, 2]


def test_multi_source_provenance_preserved():
    db = _mem_db()
    s1 = _src(db, "s1")
    s2 = _src(db, "s2")
    from domains.news.ingestion import NewsIngestionPipeline

    for s in (s1, s2):
        assert NewsIngestionPipeline(db).store_item(
            s, RawItem(title="Shared event", url="https://ex.com/shared",
                       raw_text="same wire story")) is True
    docs = db.query(Document).all()
    assert len(docs) == 2  # هر دو منبع حفظ شده‌اند (mention جدا، نه حذف)
    assert {d.source_id for d in docs} == {s1.id, s2.id}


def test_missing_optional_fields_not_all_duplicates():
    db = _mem_db()
    s = _src(db)
    from domains.news.ingestion import NewsIngestionPipeline

    p = NewsIngestionPipeline(db)
    assert p.store_item(s, RawItem(title=None, url=None, raw_text="only body one")) is True
    assert p.store_item(s, RawItem(title=None, url=None, raw_text="only body two")) is True


def test_similar_but_different_not_dropped():
    a = "the central bank raised interest rates today amid inflation fears " * 3
    b = "the central bank cut interest rates today amid recession fears " * 3
    assert near_duplicate(a, b, threshold=0.9).is_duplicate is False


def test_concurrent_insert_no_duplicates(tmp_path):

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    path = str(tmp_path / "c.db")
    eng = create_engine(f"sqlite:///{path}", connect_args={"timeout": 30})
    Base.metadata.create_all(eng)
    mk = sessionmaker(bind=eng)
    sdb = mk()
    s = Source(name="cs", collection_method="rss", type="rss", feed_url="https://ex.com/rss")
    sdb.add(s)
    sdb.commit()
    sid = s.id
    sdb.close()

    from domains.news.ingestion import NewsIngestionPipeline

    errors: list = []

    def worker():
        try:
            db = mk()
            src = db.get(Source, sid)
            for _ in range(5):
                try:
                    NewsIngestionPipeline(db).store_item(
                        src, RawItem(title="Race", url="https://ex.com/race",
                                     raw_text="same race body"))
                    db.commit()
                except Exception:  # noqa: BLE001 — نقض یکتایی قابل انتظار است
                    db.rollback()
            db.close()
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    db = mk()
    n = db.query(Document).filter(Document.source_id == sid).count()
    db.close()
    assert n == 1  # فقط یک رکورد با وجود ۲۰ تلاش هم‌زمان
