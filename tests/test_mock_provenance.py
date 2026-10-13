"""Mock provenance guards — helper سه‌حالته + پنج guard در حالت production.

قرارداد: فقط رکورد صریحاً mock در production رد می‌شود؛ unknown هرگز مدرک
نیست و فیلتر نمی‌شود؛ dev/test رفتار قبلی را دارد. تاریخچه حذف نمی‌شود.
"""
from __future__ import annotations

import asyncio
import json

from backend.database.models.article import Article
from backend.database.models.claim import Claim
from backend.database.models.document import (
    Document,
    is_mock_record,
    provenance_of,
)
from backend.database.models.event import Event
from backend.database.models.source import Source
from tests.conftest import TestingSession


def _mk_source(db, name="PSrc"):
    src = Source(name=name, domain="e.local", type="rss", active=True)
    db.add(src)
    db.commit()
    return src


def _mk_doc(db, src, title, body, *, mock=None):
    meta = None if mock is None else json.dumps({"mock": mock})
    doc = Document(source_id=src.id, title=title, raw_text=body, doc_metadata=meta)
    db.add(doc)
    db.commit()
    return doc


def _mk_article(db, doc, title, *, status="pending", cluster=None):
    art = Article(document_id=doc.id, title=title, summary=title,
                  classification_status=status, duplicate_cluster=cluster)
    db.add(art)
    db.commit()
    return art


def _prod(monkeypatch):
    """حالت production اجباری برای تست guardها (بدون provider واقعی)."""
    from backend.core.config import get_settings

    monkeypatch.setenv("MOCK_MODE", "false")
    get_settings.cache_clear()


# --- helper: شش حالت metadata ---
def test_provenance_matrix():
    assert provenance_of(json.dumps({"mock": True})) == "mock"
    assert provenance_of(json.dumps({"mock": False})) == "real"
    assert provenance_of(None) == "unknown"
    assert provenance_of("") == "unknown"
    assert provenance_of("{not json") == "unknown"
    assert provenance_of(json.dumps(["mock"])) == "unknown"
    assert provenance_of(json.dumps({"mock": "true"})) == "unknown"
    assert provenance_of(json.dumps({"mock": 1})) == "unknown"
    assert is_mock_record(json.dumps({"mock": True})) is True
    assert is_mock_record(json.dumps({"mock": False})) is False
    assert is_mock_record(None) is False


# --- guard 1: classifier ---
def test_classifier_skips_mock_in_prod(monkeypatch):
    _prod(monkeypatch)
    from domains.news.classifier import ArticleClassifier

    db = TestingSession()
    src = _mk_source(db)
    mock_doc = _mk_doc(db, src, "Mock headline", "Mock body text here.", mock=True)
    real_doc = _mk_doc(db, src, "Real headline", "Real body text here.")
    _mk_article(db, mock_doc, "Mock headline")
    _mk_article(db, real_doc, "Real headline")
    out = asyncio.run(ArticleClassifier(db).classify_pending(limit=10))
    assert out.skipped == 1
    assert out.classified + out.failed == 1  # واقعی تلاش شد، رد نشد
    rows = {a.title: a for a in db.query(Article).all()}
    assert rows["Mock headline"].classification_status == "pending"
    assert rows["Mock headline"].classification_attempts in (None, 0)
    db.close()


def test_classifier_processes_mock_in_dev():
    db = TestingSession()
    src = _mk_source(db, "DevSrc")
    doc = _mk_doc(db, src, "Dev mock", "Dev mock body content here.", mock=True)
    _mk_article(db, doc, "Dev mock")
    from domains.news.classifier import ArticleClassifier

    out = asyncio.run(ArticleClassifier(db).classify_pending(limit=10))
    assert out.skipped == 0 and out.classified == 1  # رفتار قبلی dev حفظ شد
    db.close()


# --- guard 2: events (سیاست خوشه) ---
def _mk_cluster(db, src, name, *, mock=None, real_misc=False):
    doc = _mk_doc(db, src, f"{name} headline", f"{name} body content here.", mock=mock)
    art = _mk_article(db, doc, f"{name} headline", status="done", cluster=name)
    if real_misc:
        doc2 = _mk_doc(db, src, f"{name} other", f"{name} other body here.")
        _mk_article(db, doc2, f"{name} other", status="done", cluster=name)
    return art


def test_events_skip_all_mock_cluster_in_prod(monkeypatch):
    _prod(monkeypatch)
    from domains.events.extractor import EventExtractor

    db = TestingSession()
    src = _mk_source(db, "EvSrc")
    _mk_cluster(db, src, "mockc", mock=True)
    out = asyncio.run(EventExtractor(db).run(limit=10))
    assert out.skipped == 1 and out.events_created == 0
    assert db.query(Event).count() == 0
    db.close()


def test_events_process_all_real_cluster_in_prod(monkeypatch):
    _prod(monkeypatch)
    from domains.events.extractor import EventExtractor

    db = TestingSession()
    src = _mk_source(db, "EvReal")
    _mk_cluster(db, src, "realc")
    out = asyncio.run(EventExtractor(db).run(limit=10))
    assert out.skipped == 0 and out.events_created == 1
    db.close()


def test_events_skip_mixed_cluster_in_prod(monkeypatch):
    _prod(monkeypatch)
    from domains.events.extractor import EventExtractor

    db = TestingSession()
    src = _mk_source(db, "EvMix")
    _mk_cluster(db, src, "mixc", mock=True, real_misc=True)
    out = asyncio.run(EventExtractor(db).run(limit=10))
    assert out.skipped == 1 and out.events_created == 0  # محافظه‌کارانه
    db.close()


def test_events_process_unknown_cluster_in_prod(monkeypatch):
    _prod(monkeypatch)
    from domains.events.extractor import EventExtractor

    db = TestingSession()
    src = _mk_source(db, "EvUnk")
    doc = _mk_doc(db, src, "Plain headline", "Plain body content here.")  # بدون marker
    _mk_article(db, doc, "Plain headline", status="done", cluster="unkc")
    out = asyncio.run(EventExtractor(db).run(limit=10))
    assert out.skipped == 0 and out.events_created == 1  # unknown فیلتر نمی‌شود
    db.close()


# --- guard 3: claims ---
def _mk_event_with_articles(db, src, name, *, mock=None):
    doc = _mk_doc(db, src, f"{name} headline", f"{name} body content here.", mock=mock)
    art = _mk_article(db, doc, f"{name} headline", status="done")
    event = Event(event_type="test_type", action=f"{name} action happened here.",
                  actors=json.dumps(["Actor"]), sources=json.dumps([str(src.id)]),
                  claims_extracted=False)
    db.add(event)
    db.commit()
    art.event_id = event.id
    db.commit()
    return event


def test_claims_skip_mock_event_in_prod(monkeypatch):
    _prod(monkeypatch)
    from domains.claims.extractor import ClaimExtractor

    db = TestingSession()
    src = _mk_source(db, "ClSrc")
    _mk_event_with_articles(db, src, "mcev", mock=True)
    out = asyncio.run(ClaimExtractor(db).run(limit=10))
    assert out.skipped == 1 and out.claims_created == 0
    db.close()


def test_claims_process_real_event_in_prod(monkeypatch):
    _prod(monkeypatch)
    from domains.claims.extractor import ClaimExtractor

    db = TestingSession()
    src = _mk_source(db, "ClReal")
    _mk_event_with_articles(db, src, "rlev")
    out = asyncio.run(ClaimExtractor(db).run(limit=10))
    assert out.skipped == 0 and out.claims_created >= 1
    db.close()


# --- guard 4: evidence ---
def _mk_claim(db, src, name, *, mock=None):
    event = _mk_event_with_articles(db, src, name, mock=mock)
    event.claims_extracted = True
    claim = Claim(event_id=event.id, subject="Actor", predicate="did",
                  object="thing", claim_type="test_type",
                  verification_status="unverified", evidence_extracted=False)
    db.add(claim)
    db.commit()
    return claim


def test_evidence_skips_mock_claim_without_burning_attempts(monkeypatch):
    _prod(monkeypatch)
    from domains.claims.evidence import EvidenceEngine

    db = TestingSession()
    src = _mk_source(db, "EvdSrc")
    claim = _mk_claim(db, src, "mev", mock=True)
    out = asyncio.run(EvidenceEngine(db).run(limit=10))
    assert out.skipped == 1 and out.claims_processed == 0
    db.refresh(claim)
    assert (claim.evidence_attempts or 0) == 0  # attempt نسوخت
    assert claim.evidence_extracted is False  # وضعیت دست‌نخورده
    db.close()


# --- guard 5: worldstate ---
def test_worldstate_excludes_mock_event_in_prod(monkeypatch):
    _prod(monkeypatch)
    from backend.database.models.world_state import WorldState
    from domains.worldstate.builder import WorldStateBuilder

    db = TestingSession()
    src = _mk_source(db, "WsSrc")
    _mk_event_with_articles(db, src, "wsmock", mock=True)
    snap = WorldStateBuilder(db).build()
    import uuid as _uuid

    row = db.query(WorldState).filter(
        WorldState.id == _uuid.UUID(str(snap.snapshot_id))).one_or_none()
    notes = getattr(snap, "notes", None) or (row.notes if row else "")
    assert "mock_skipped" in (notes or "")
    db.close()


# --- بدون حذف تاریخچه + استقلال ربات ---
def test_guards_never_delete_rows(monkeypatch):
    _prod(monkeypatch)
    from domains.claims.extractor import ClaimExtractor
    from domains.events.extractor import EventExtractor
    from domains.news.classifier import ArticleClassifier

    db = TestingSession()
    src = _mk_source(db, "NoDel")
    _mk_cluster(db, src, "ndmock", mock=True)
    n_docs = db.query(Document).count()
    n_arts = db.query(Article).count()
    asyncio.run(ArticleClassifier(db).classify_pending(limit=10))
    asyncio.run(EventExtractor(db).run(limit=10))
    asyncio.run(ClaimExtractor(db).run(limit=10))
    assert db.query(Document).count() == n_docs
    assert db.query(Article).count() == n_arts
    assert db.query(Event).count() == 0
    db.close()


def test_source_bot_untouched():
    import source_bot.priority_engine as pe
    import source_bot.runner  # noqa: F401 — فقط importپذیری

    res = pe.score_item(title="Routine summary", body="calm text " * 30)
    assert res.level in ("P0", "P1", "P2", "P3", "P4")
