"""Tests for F13 local archive core (offline)."""
from __future__ import annotations

import json
import os
import tempfile
import zipfile

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.archive.service import (
    archive_settings,
    build_archive_zip,
    is_eligible,
    measure_storage,
    validate_archive_zip,
)
from tests.conftest import TestingSession


def _seed_article(*, importance=5, status="done", raw_text="hello world", content_hash="abc123",
                  meta='{"provider":"groq","model":"openai/gpt-oss-20b","mock":false}',
                  uncertainty=0.1):
    session = TestingSession()
    try:
        src = Source(name=f"S-{os.urandom(4).hex()}", domain="t.local", type="rss", active=True)
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="t", raw_text=raw_text, content_hash=content_hash,
                       doc_metadata=meta, revision=1)
        session.add(doc)
        session.flush()
        art = Article(document_id=doc.id, title="news", summary="s", importance=importance,
                      classification_status=status, classification_meta=meta,
                      uncertainty=uncertainty, decided_by="rules", confidence=0.8)
        session.add(art)
        session.commit()
        return str(art.id)
    finally:
        session.close()


def test_archive_settings_defaults():
    s = archive_settings()
    assert s["ARCHIVE_ENABLED"] is False
    assert s["TELEGRAM_ARCHIVE_ENABLED"] is False
    assert s["ARCHIVE_AUTO_PURGE_ENABLED"] is False
    assert s["PURGE_DRY_RUN"] is True
    assert s["ARCHIVE_MAX_ZIP_BYTES"] == 18_000_000


def test_eligible_article():
    aid = _seed_article()
    session = TestingSession()
    try:
        import uuid as _uuid
        art = session.get(Article, _uuid.UUID(aid))
        ok, reasons = is_eligible(session, art)
        assert ok is True, reasons
    finally:
        session.close()


def test_ineligible_pending():
    aid = _seed_article(status="pending")
    session = TestingSession()
    try:
        import uuid as _uuid
        art = session.get(Article, _uuid.UUID(aid))
        ok, reasons = is_eligible(session, art)
        assert ok is False
        assert "classification_not_done" in reasons
    finally:
        session.close()


def test_ineligible_protected_p0():
    aid = _seed_article(importance=1)
    session = TestingSession()
    try:
        import uuid as _uuid
        art = session.get(Article, _uuid.UUID(aid))
        ok, reasons = is_eligible(session, art)
        assert ok is False
        assert "protected_priority_p0_p1" in reasons
    finally:
        session.close()


def test_build_and_validate_zip():
    aid = _seed_article()
    session = TestingSession()
    try:
        import uuid as _uuid
        art = session.get(Article, _uuid.UUID(aid))
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "archive.zip")
        res = build_archive_zip(session, [str(art.id)], out, batch_id="batch-1")
        assert res.article_ids == [str(art.id)]
        assert os.path.exists(out)
        v = validate_archive_zip(out)
        assert v["ok"] is True, v["errors"]
        assert v["counts"]["articles"] == 1
        # check required files
        with zipfile.ZipFile(out) as zf:
            names = zf.namelist()
        for f in ["manifest.json", "articles.jsonl", "SHA256SUMS.txt", "REPORT.md"]:
            assert f in names
        # manifest article_count
        with zipfile.ZipFile(out) as zf:
            m = json.loads(zf.read("manifest.json"))
        assert m["article_count"] == 1
        assert m["mock_as_real"] is False
    finally:
        session.close()


def test_measure_storage():
    _seed_article()
    session = TestingSession()
    try:
        m = measure_storage(session)
        assert m["counts"]["articles"] >= 1
        assert "approx_text_bytes" in m
    finally:
        session.close()
