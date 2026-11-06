"""Restore tests for F13-LOCAL-2."""
from __future__ import annotations

import os
import tempfile
import uuid

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.archive.restore import restore_dry_run, restore_from_zip
from domains.archive.service import build_archive_zip, check_zip_security
from tests.conftest import TestingSession


def _seed_article(session):
    src = Source(name="S-" + uuid.uuid4().hex[:6], domain="t.local", type="rss", active=True)
    session.add(src)
    session.flush()
    doc = Document(source_id=src.id, title="t", raw_text="hello world", content_hash="h1",
                   doc_metadata='{"mock":false}', revision=1)
    session.add(doc)
    session.flush()
    art = Article(document_id=doc.id, title="news", summary="s", importance=5,
                  classification_status="done", classification_meta='{"mock":false}',
                  uncertainty=0.1, decided_by="rules", confidence=0.8)
    session.add(art)
    session.commit()
    return str(art.id), art, doc


def test_restore_dry_run_and_restore():
    session = TestingSession()
    try:
        aid, art, doc = _seed_article(session)
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "a.zip")
        build_archive_zip(session, [aid], out, batch_id="b1")
        # dry run
        preview = restore_dry_run(session, out)
        assert preview["ok"] is True
        assert preview["total_records"] == 1
        assert preview["restorable"] == 0  # already exists
        assert preview["duplicates"] == 1
        # actual restore: should skip duplicate
        res = restore_from_zip(session, out)
        assert res["ok"] is True
        assert res["skipped"] == 1
        assert res["restored"] == 0
    finally:
        session.close()


def test_restore_new_article():
    s1 = TestingSession()
    aid = None
    try:
        aid, art, doc = _seed_article(s1)
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "a.zip")
        build_archive_zip(s1, [aid], out, batch_id="b2")
    finally:
        s1.close()
    # new db session (same in-memory? TestingSession shares engine) -> article exists, so delete it first to simulate new
    s2 = TestingSession()
    try:
        import uuid as _u
        art = s2.get(Article, _u.UUID(aid))
        if art is not None:
            s2.delete(art)
            if art.document is not None:
                s2.delete(art.document)
            s2.commit()
        res = restore_from_zip(s2, out)
        assert res["ok"] is True
        assert res["restored"] == 1
    finally:
        s2.close()


def test_restore_conflict_not_overwrite():
    session = TestingSession()
    try:
        aid, art, doc = _seed_article(session)
        # change hash to create conflict scenario in archive? Rebuild with modified doc hash
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "a.zip")
        # tamper content_hash in DB before archive
        doc.content_hash = "different"
        session.commit()
        build_archive_zip(session, [aid], out, batch_id="b3")
        # revert db hash to original to create mismatch
        doc.content_hash = "h1"
        session.commit()
        res = restore_from_zip(session, out)
        # existing article has hash h1, archive has different -> conflict, no overwrite
        assert res["conflicts"] >= 1
        assert res["restored"] == 0
    finally:
        session.close()


def test_security_path_traversal():
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "bad.zip")
    import zipfile
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("../evil.txt", "x")
    ok, errs = check_zip_security(p)
    assert ok is False
    assert any("unsafe path" in e for e in errs)


def _seed_second_article(session, source_id):
    doc = Document(source_id=source_id, title="t2", raw_text="second body", content_hash="h2",
                   doc_metadata='{"mock":false,"adapter":"rss"}', revision=2)
    session.add(doc)
    session.flush()
    art = Article(document_id=doc.id, title="news2", summary="s2", importance=4,
                  classification_status="done", classification_meta='{"mock":false}',
                  uncertainty=0.1, decided_by="rules", confidence=0.8)
    session.add(art)
    session.commit()
    return str(art.id), doc


def _rewrite_entry(path, name, new_content):
    """Replace one zip entry and recompute SHA256SUMS so validation still passes."""
    import hashlib
    import zipfile

    with zipfile.ZipFile(path) as zf:
        items = {n: zf.read(n) for n in zf.namelist()}
    items[name] = new_content
    sha_lines = []
    for entry, content in items.items():
        if entry == "SHA256SUMS.txt":
            continue
        sha_lines.append(f"{hashlib.sha256(content).hexdigest()}  {entry}")
    items["SHA256SUMS.txt"] = ("\n".join(sha_lines) + "\n").encode("utf-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for entry, content in items.items():
            zf.writestr(entry, content)


def test_restore_preserves_source_and_provenance():
    s1 = TestingSession()
    try:
        aid, art, doc = _seed_article(s1)
        source_id, doc_metadata, content_hash, revision = (
            doc.source_id, doc.doc_metadata, doc.content_hash, doc.revision
        )
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "a.zip")
        build_archive_zip(s1, [aid], out, batch_id="prov1")
    finally:
        s1.close()

    s2 = TestingSession()
    try:
        art = s2.get(Article, uuid.UUID(aid))
        if art is not None:
            s2.delete(art)
            if art.document is not None:
                s2.delete(art.document)
            s2.commit()
        res = restore_from_zip(s2, out)
        assert res["ok"] is True, res
        assert res["restored"] == 1
        restored = s2.get(Article, uuid.UUID(aid))
        assert restored is not None
        new_doc = restored.document
        assert new_doc is not None
        # identity and provenance survive the round-trip
        assert str(new_doc.source_id) == str(source_id)
        assert new_doc.doc_metadata == doc_metadata
        assert new_doc.content_hash == content_hash
        assert new_doc.revision == revision
    finally:
        s2.close()


def test_restore_is_all_or_nothing_on_bad_record():
    session = TestingSession()
    try:
        aid, art, doc = _seed_article(session)
        aid2, doc2 = _seed_second_article(session, doc.source_id)
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "pair.zip")
        build_archive_zip(session, [aid, aid2], out, batch_id="pair")

        # Second record gets an unusable id; the archive still validates so the
        # failure happens mid-write, after the first record was already flushed.
        import json
        import zipfile
        with zipfile.ZipFile(out) as zf:
            lines = zf.read("articles.jsonl").decode("utf-8").splitlines()
        records = [json.loads(ln) for ln in lines if ln.strip()]
        records[1]["article_id"] = "not-a-uuid"
        _rewrite_entry(out, "articles.jsonl",
                       ("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n").encode("utf-8"))

        for article_id in (aid, aid2):
            a = session.get(Article, uuid.UUID(article_id))
            if a is not None:
                session.delete(a)
                if a.document is not None:
                    session.delete(a.document)
        session.commit()
        assert session.query(Article).count() == 0

        res = restore_from_zip(session, out)
        assert res["ok"] is False
        assert res["restored"] == 0
        assert res.get("rolled_back") is True
        assert res["errors"]
        # the already-flushed first record must not survive the failure
        assert session.query(Article).count() == 0
        assert session.query(Document).count() == 0
    finally:
        session.close()


def test_dry_run_no_changes():
    session = TestingSession()
    try:
        aid, art, doc = _seed_article(session)
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "a.zip")
        build_archive_zip(session, [aid], out, batch_id="b4")
        before = session.query(Article).count()
        r = restore_from_zip(session, out, dry_run=True)
        assert r["dry_run"] is True
        after = session.query(Article).count()
        assert before == after
    finally:
        session.close()
