"""Relationship restore tests for F15-T2-CLOSE."""
from __future__ import annotations

import os
import tempfile
import uuid

from backend.database.models.article import Article
from backend.database.models.claim import Claim, Evidence
from backend.database.models.document import Document
from backend.database.models.entity import Entity, EntityRelationship
from backend.database.models.event import Event
from backend.database.models.source import Source
from domains.archive.restore import restore_from_zip
from domains.archive.service import build_archive_zip, validate_archive_zip
from tests.conftest import TestingSession


def test_restore_event_claim_evidence_entity_graph():
    session = TestingSession()
    try:
        src = Source(name="S-" + uuid.uuid4().hex[:6], domain="t.local", type="rss", active=True)
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="t", raw_text="hello", content_hash="h1",
                       doc_metadata='{"mock":false}', revision=1)
        session.add(doc)
        session.flush()
        ev = Event(event_type="conflict", action="bank raised rates", surprise=0.8)
        session.add(ev)
        session.flush()
        claim = Claim(event_id=ev.id, subject="Acme", predicate="raised", object="rates",
                      verification_status="verified")
        session.add(claim)
        session.flush()
        evd = Evidence(claim_id=claim.id, direction="supports")
        session.add(evd)
        session.flush()
        # entities + edge
        e1 = Entity(type="org", canonical_name="Acme", display_name="Acme Corp")
        e2 = Entity(type="indicator", canonical_name="rates", display_name="Rates")
        session.add_all([e1, e2])
        session.flush()
        edge = EntityRelationship(from_entity_id=e1.id, to_entity_id=e2.id, relation="affects")
        session.add(edge)
        session.flush()
        art = Article(document_id=doc.id, title="news", summary="s", importance=5,
                      classification_status="done", classification_meta='{"mock":false}',
                      uncertainty=0.1, decided_by="rules", confidence=0.8, event_id=ev.id,
                      entities='["Acme","rates"]')
        session.add(art)
        session.commit()
        aid = str(art.id)
        eid = str(ev.id)
        cid = str(claim.id)
        evid = str(evd.id)
        e1id = str(e1.id)
        e2id = str(e2.id)
        edgeid = str(edge.id)
        tmp = tempfile.mkdtemp()
        out = os.path.join(tmp, "r.zip")
        res = build_archive_zip(session, [aid], out, batch_id="relbatch")
        assert res.article_ids == [aid]
        v = validate_archive_zip(out)
        assert v["ok"] is True
        # verify serialized
        import json
        import zipfile
        with zipfile.ZipFile(out) as zf:
            rec = json.loads(zf.read("articles.jsonl").decode().strip().splitlines()[0])
        assert rec.get("event_record") is not None
        assert len(rec.get("entity_records", [])) >= 2
        assert len(rec.get("graph_edges", [])) >= 1
    finally:
        session.close()

    session2 = TestingSession()
    try:
        import uuid as _u
        # remove all
        for mid, model in ((evid, Evidence), (cid, Claim), (eid, Event), (edgeid, EntityRelationship),
                           (e1id, Entity), (e2id, Entity)):
            r = session2.get(model, _u.UUID(mid))
            if r is not None:
                session2.delete(r)
        a = session2.get(Article, _u.UUID(aid))
        if a is not None:
            session2.delete(a)
            if a.document is not None:
                session2.delete(a.document)
        session2.commit()

        r = restore_from_zip(session2, out)
        print("restore result:", r)
        assert r["ok"] is True
        assert r["restored"] == 1

        # verify event/claim/evidence
        assert session2.get(Event, _u.UUID(eid)) is not None
        assert session2.get(Claim, _u.UUID(cid)) is not None
        assert session2.get(Evidence, _u.UUID(evid)) is not None
        # verify entity/graph
        assert session2.get(Entity, _u.UUID(e1id)) is not None
        assert session2.get(Entity, _u.UUID(e2id)) is not None
        assert session2.get(EntityRelationship, _u.UUID(edgeid)) is not None
        art2 = session2.get(Article, _u.UUID(aid))
        assert art2.event_id == _u.UUID(eid)
        # idempotency
        r2 = restore_from_zip(session2, out)
        assert r2["skipped"] >= 1 or r2["restored"] == 0
        print("ENTITY/GRAPH RESTORE OK")
    finally:
        session2.close()
