"""Split test for F13."""
from __future__ import annotations

import os
import tempfile
import uuid

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.archive.service import build_archive_zips, validate_archive_zip
from tests.conftest import TestingSession


def test_split_and_validate_parts():
    session = TestingSession()
    try:
        ids = []
        for i in range(3):
            src = Source(name="S-" + uuid.uuid4().hex[:6], domain="t.local", type="rss", active=True)
            session.add(src)
            session.flush()
            doc = Document(source_id=src.id, title="t", raw_text="hello world",
                           content_hash="h" + str(i), doc_metadata='{"mock":false}', revision=1)
            session.add(doc)
            session.flush()
            art = Article(document_id=doc.id, title="news" + str(i), summary="s", importance=5,
                          classification_status="done", classification_meta='{"mock":false}',
                          uncertainty=0.1, decided_by="rules", confidence=0.8)
            session.add(art)
            session.commit()
            ids.append(str(art.id))
        tmp = tempfile.mkdtemp()
        os.environ["ARCHIVE_MAX_ZIP_BYTES"] = "200"
        res = build_archive_zips(session, ids, tmp, batch_id="splitbatch")
        assert len(res) == 3
        for r in res:
            v = validate_archive_zip(r.zip_path)
            assert v["ok"] is True, v["errors"]
            assert v["manifest"].get("total_parts") == 3
    finally:
        session.close()
        os.environ.pop("ARCHIVE_MAX_ZIP_BYTES", None)
