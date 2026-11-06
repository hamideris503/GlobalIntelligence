"""Entity hardening tests for F15-T2.1."""
from __future__ import annotations

import os
import tempfile
import uuid

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.entity import Entity
from backend.database.models.source import Source
from domains.archive.restore import restore_from_zip
from domains.archive.service import build_archive_zip
from tests.conftest import TestingSession


def test_entity_aliases_preserved():
    session = TestingSession()
    try:
        src = Source(name="S-" + uuid.uuid4().hex[:6], domain="t.local", type="rss", active=True)
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="t", raw_text="hello", content_hash="h1",
                       doc_metadata='{"mock":false}', revision=1)
        session.add(doc)
        session.flush()
        e = Entity(type="org", canonical_name="Acme", display_name="Acme Corp", aliases='["ACME","Acme Inc"]')
        session.add(e)
        session.flush()
        art = Article(document_id=doc.id, title="news", summary="s", importance=5,
                      classification_status="done", classification_meta='{"mock":false}',
                      uncertainty=0.1, decided_by="rules", confidence=0.8,
                      entities='["Acme"]')
        session.add(art)
        session.commit()
        aid = str(art.id)
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "a.zip")
        build_archive_zip(session, [aid], out, batch_id="aliasbatch")
        import json
        import zipfile
        with zipfile.ZipFile(out) as zf:
            rec = json.loads(zf.read("articles.jsonl").decode().strip().splitlines()[0])
        ents = rec.get("entity_records", [])
        assert any(x.get("aliases") == '["ACME","Acme Inc"]' for x in ents)
    finally:
        session.close()


def test_same_name_different_type_not_merged():
    session = TestingSession()
    try:
        src = Source(name="S-" + uuid.uuid4().hex[:6], domain="t.local", type="rss", active=True)
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="t", raw_text="hello", content_hash="h1",
                       doc_metadata='{"mock":false}', revision=1)
        session.add(doc)
        session.flush()
        e1 = Entity(type="org", canonical_name="X", display_name="X org")
        e2 = Entity(type="indicator", canonical_name="X", display_name="X ind")
        session.add_all([e1, e2])
        session.flush()
        art = Article(document_id=doc.id, title="news", summary="s", importance=5,
                      classification_status="done", classification_meta='{"mock":false}',
                      uncertainty=0.1, decided_by="rules", confidence=0.8,
                      entities='["X"]')
        session.add(art)
        session.commit()
        aid = str(art.id)
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "a.zip")
        build_archive_zip(session, [aid], out, batch_id="typebatch")
        import json
        import zipfile
        with zipfile.ZipFile(out) as zf:
            rec = json.loads(zf.read("articles.jsonl").decode().strip().splitlines()[0])
        ents = rec.get("entity_records", [])
        # both types selected
        types = {x.get("type") for x in ents}
        assert "org" in types and "indicator" in types
    finally:
        session.close()


def test_entity_idempotent_restore():
    session = TestingSession()
    try:
        src = Source(name="S-" + uuid.uuid4().hex[:6], domain="t.local", type="rss", active=True)
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="t", raw_text="hello", content_hash="h1",
                       doc_metadata='{"mock":false}', revision=1)
        session.add(doc)
        session.flush()
        e = Entity(type="org", canonical_name="Acme", display_name="Acme Corp", aliases='["ACME"]')
        session.add(e)
        session.flush()
        art = Article(document_id=doc.id, title="news", summary="s", importance=5,
                      classification_status="done", classification_meta='{"mock":false}',
                      uncertainty=0.1, decided_by="rules", confidence=0.8,
                      entities='["Acme"]')
        session.add(art)
        session.commit()
        aid = str(art.id)
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "a.zip")
        build_archive_zip(session, [aid], out, batch_id="idempbatch")
    finally:
        session.close()

    session2 = TestingSession()
    try:
        import uuid as _u
        # remove seeded article+doc+entity to simulate fresh target
        a = session2.query(Article).filter(Article.id == _u.UUID(aid)).first()
        if a is not None:
            session2.delete(a)
            if a.document is not None:
                session2.delete(a.document)
        for e in session2.query(Entity).filter(Entity.canonical_name == "Acme").all():
            session2.delete(e)
        session2.commit()
        r = restore_from_zip(session2, out)
        assert r["ok"] is True
        assert r["restored"] == 1
        # second restore: no duplicate entity
        r2 = restore_from_zip(session2, out)
        assert r2["restored"] == 0
        # entity still one
        cnt = session2.query(Entity).filter(Entity.canonical_name == "Acme").count()
        assert cnt == 1
    finally:
        session2.close()
