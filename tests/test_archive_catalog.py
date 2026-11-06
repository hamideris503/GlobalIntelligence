"""Catalog persistence test for F13-LOCAL-2."""
from __future__ import annotations

import os
import tempfile
import uuid

from backend.database.models.archive_catalog import ArchiveArticle
from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.archive.catalog import get_archive, list_archives, record_archive
from domains.archive.service import build_archive_zip
from tests.conftest import TestingSession


def test_record_and_list_archive():
    session = TestingSession()
    try:
        src = Source(name="S-" + uuid.uuid4().hex[:6], domain="t.local", type="rss", active=True)
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="t", raw_text="hello", content_hash="h1",
                       doc_metadata='{"mock":false}', revision=1)
        session.add(doc)
        session.flush()
        art = Article(document_id=doc.id, title="news", summary="s", importance=5,
                      classification_status="done", classification_meta='{"mock":false}',
                      uncertainty=0.1, decided_by="rules", confidence=0.8)
        session.add(art)
        session.commit()
        aid = str(art.id)
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "c.zip")
        res = build_archive_zip(session, [aid], out, batch_id="catbatch")
        row = record_archive(session, res.manifest, out, res.article_ids, res.omitted,
                             eligibility={aid: "ELIGIBLE"})
        assert row.archive_id == "catbatch"
        assert row.validation_status == "valid"
        assert get_archive(session, "catbatch") is not None
        assert len(list_archives(session)) >= 1
        # The per-article fingerprint must come from the archive, not be left NULL:
        # conflict detection on restore depends on these two fields.
        item = (
            session.query(ArchiveArticle)
            .filter(ArchiveArticle.archive_id == "catbatch")
            .one()
        )
        assert item.revision == 1
        assert item.content_hash == "h1"
    finally:
        session.close()
