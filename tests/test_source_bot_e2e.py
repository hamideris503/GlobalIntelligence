"""E2E: خبر مصنوعی یکتا از Source Bot تا Evidence — دیتابیس تست، gateway واقعیِ mock.

هیچ داده واقعی لمس نمی‌شود (sqlite حافظه‌ای).
بخش‌های نیازمند سرویس واقعی: AI واقعی (credential)، Postgres، شبکه (همه جدا گزارش می‌شوند).
"""
from __future__ import annotations

import asyncio

from backend.database.base import Base
from backend.database.models.article import Article
from backend.database.models.claim import Claim
from backend.database.models.document import Document
from backend.database.models.event import Event
from backend.database.models.evidence import Evidence
from backend.database.models.source import Source
from domains.news.fetchers import RawItem


def _mem_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


TITLE = "Breaking: major earthquake strikes region, emergency response underway"
BODY = ("A major earthquake struck the region, triggering an emergency response "
        "as rescue teams warn of aftershocks and urgent humanitarian needs. " * 6)
URL = "https://example.test/e2e/harbor-festival"


def _counts(db):
    return {
        "documents": db.query(Document).count(),
        "articles": db.query(Article).count(),
        "events": db.query(Event).count(),
        "claims": db.query(Claim).count(),
        "evidence": db.query(Evidence).count(),
    }


def test_e2e_bot_to_evidence():
    from domains.claims.evidence import EvidenceEngine
    from domains.claims.extractor import ClaimExtractor
    from domains.events.extractor import EventExtractor
    from domains.news.classifier import ArticleClassifier
    from domains.news.dedup_service import DedupService
    from source_bot.deduplicator import canonical_url
    from source_bot.normalizer import normalize_item
    from source_bot.output import deliver
    from source_bot.priority_engine import score_item

    db = _mem_db()
    src = Source(name="e2e-src", collection_method="rss", type="rss",
                 feed_url="https://example.test/rss")
    db.add(src)
    db.commit()

    item = RawItem(title=TITLE, url=URL, raw_text=BODY, author="Test Desk")

    # 1) normalize قرارداد موجود
    norm = normalize_item(item)
    assert norm.content_hash and norm.hash
    assert norm.title == TITLE and norm.url == URL

    # 2) اولویت دریافت (جدا از importance تحلیلی)
    pr = score_item(title=item.title, body=item.raw_text, has_author=True)
    assert pr.level in ("P0", "P1", "P2", "P3", "P4")

    # 3) تحویل به pipeline موجود
    assert deliver(db, src, item, priority=pr.level, score=pr.score,
                   reason=f"rules score={pr.score}", priority_source="rules",
                   priority_status="RULES_ONLY", duplicate_status="new",
                   canonical_url=canonical_url(URL), final_url=URL) is True
    doc = db.query(Document).first()
    assert doc.ingestion_priority == pr.level and doc.duplicate_status == "new"
    art = db.query(Article).first()
    assert art is not None and art.classification_status == "pending"
    assert art.importance is None  # ربات importance تحلیلی را دست نمی‌زند

    # 4) dedup: بدون خوشه تکراری
    summary = DedupService(db).run(limit=10)
    assert summary["duplicate_clusters"] == 0

    # 5) classify با mock واقعی gateway
    async def chain():
        out = await ArticleClassifier(db).classify_pending(limit=10)
        assert out.classified >= 1
        ev = await EventExtractor(db).run(limit=10)
        assert ev.events_created >= 1
        cl = await ClaimExtractor(db).run(limit=10)
        assert cl.claims_created >= 1
        ew = await EvidenceEngine(db).run(limit=10)
        assert ew.supports + ew.contradicts >= 1
    asyncio.run(chain())

    counts = _counts(db)
    assert counts == {"documents": 1, "articles": 1, "events": 1,
                      "claims": counts["claims"], "evidence": counts["evidence"]}
    assert counts["claims"] >= 1 and counts["evidence"] >= 1
    db.close()


def test_e2e_rerun_no_dup_but_update_and_new_kept():
    from source_bot.output import deliver

    db = _mem_db()
    src = Source(name="e2e-src2", collection_method="rss", type="rss",
                 feed_url="https://example.test/rss")
    db.add(src)
    db.commit()
    kw = dict(priority="P2", score=55.0, reason="r", priority_source="rules",
              priority_status="RULES_ONLY", duplicate_status="new")

    assert deliver(db, src, RawItem(title=TITLE, url=URL, raw_text=BODY), **kw) is True
    # اجرای دوباره همان خبر -> بدون رکورد جدید
    assert deliver(db, src, RawItem(title=TITLE, url=URL, raw_text=BODY), **kw) is False
    assert db.query(Document).count() == 1
    # نسخه به‌روزشده (همان URL، متن جدید) -> حفظ می‌شود، حذف نه
    assert deliver(db, src, RawItem(title=TITLE + " (updated)", url=URL,
                                    raw_text=BODY + " Extra evening program announced."),
                   **kw) is True
    assert db.query(Document).count() == 2
    # خبر واقعاً جدید -> حفظ می‌شود
    assert deliver(db, src, RawItem(title="Another synthetic dispatch",
                                    url="https://example.test/e2e/other",
                                    raw_text="A different synthetic story body."),
                   **kw) is True
    assert db.query(Document).count() == 3
    db.close()
