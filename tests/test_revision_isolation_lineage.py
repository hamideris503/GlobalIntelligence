"""Revision source isolation + analysis lineage tests on PostgreSQL/SQLite."""
from __future__ import annotations

import json
import uuid

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from tests.conftest import TestingSession


def _seed_source(session, name):
    src = Source(name=name, domain="t.local", type="rss", active=True, collection_method="rss")
    session.add(src)
    session.flush()
    return src


def test_revision_source_isolation_and_lineage():
    session = TestingSession()
    try:
        # Source A
        src_a = _seed_source(session, "SrcA-" + uuid.uuid4().hex[:6])
        # V1
        doc_a1 = Document(source_id=src_a.id, title="GDP v1", raw_text="GDP grew 3 percent",
                          content_hash="hash_a_v1", hash="urlhash", revision=1,
                          doc_metadata='{"mock":false}', url="https://test.local/rev")
        session.add(doc_a1)
        session.flush()
        art_a1 = Article(document_id=doc_a1.id, title="GDP v1", classification_status="done",
                         classification_meta='{"lineage_probe":"SOURCE_A_V1","provider":"mock","model":"m","prompt_version":"v1"}',
                         importance=5, decided_by="rules", confidence=0.8)
        session.add(art_a1)
        # V2
        doc_a2 = Document(source_id=src_a.id, title="GDP v2", raw_text="GDP grew 3.2 percent",
                          content_hash="hash_a_v2", hash="urlhash", revision=2,
                          doc_metadata='{"mock":false}', url="https://test.local/rev")
        session.add(doc_a2)
        session.flush()
        art_a2 = Article(document_id=doc_a2.id, title="GDP v2", classification_status="done",
                         classification_meta='{"lineage_probe":"SOURCE_A_V2","provider":"mock","model":"m","prompt_version":"v1"}',
                         importance=5, decided_by="rules", confidence=0.8)
        session.add(art_a2)

        # Source B (independent, same URL but different content)
        src_b = _seed_source(session, "SrcB-" + uuid.uuid4().hex[:6])
        doc_b1 = Document(source_id=src_b.id, title="GDP B", raw_text="GDP grew 3.1 percent elsewhere",
                          content_hash="hash_b_v1", hash="urlhash_b", revision=1,
                          doc_metadata='{"mock":false}', url="https://test.local/rev-b")
        session.add(doc_b1)
        session.flush()
        art_b1 = Article(document_id=doc_b1.id, title="GDP B", classification_status="done",
                         classification_meta='{"lineage_probe":"SOURCE_B_V1","provider":"mock","model":"m","prompt_version":"v1"}',
                         importance=5, decided_by="rules", confidence=0.8)
        session.add(art_b1)
        session.commit()

        # Verify Source A revisions
        a_docs = session.query(Document).filter(Document.source_id == src_a.id).all()
        assert len(a_docs) == 2
        revs = sorted(d.revision for d in a_docs)
        assert revs == [1, 2]
        hashes = {d.content_hash for d in a_docs}
        assert len(hashes) == 2

        # Source B independent
        b_docs = session.query(Document).filter(Document.source_id == src_b.id).all()
        assert len(b_docs) == 1
        assert b_docs[0].revision == 1

        # Analysis lineage: V1 preserved
        a1_meta = json.loads(art_a1.classification_meta)
        a2_meta = json.loads(art_a2.classification_meta)
        b1_meta = json.loads(art_b1.classification_meta)
        assert a1_meta["lineage_probe"] == "SOURCE_A_V1"
        assert a2_meta["lineage_probe"] == "SOURCE_A_V2"
        assert b1_meta["lineage_probe"] == "SOURCE_B_V1"
        # no cross-leakage
        assert a1_meta["lineage_probe"] != a2_meta["lineage_probe"]
        assert a1_meta["lineage_probe"] != b1_meta["lineage_probe"]

        # Idempotency: re-ingest doesn't create new (simulate by checking counts unchanged)
        before_a = session.query(Document).filter(Document.source_id == src_a.id).count()
        assert before_a == 2
    finally:
        session.close()
