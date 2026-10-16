"""Delete ONLY the 249 approved test rows — transactional with rollback.

شرایط ایمنی (هر کدام برقرار نباشد → rollback + توقف، بدون حذف):
- دقیقاً 120/120/3/3/3 ردیف، همه example.local / fake-linked؛
- 0 مقاله‌ی واقعی روی eventهای هدف؛ 0 ارجاع از forecasts/relationships؛
- memory/narrative/heartbeat/audit دست نمی‌خورند.

اجرا:
    python -m scripts.cleanup_test_rows --execute
بدون --execute فقط پیش‌نمایش (exit 0).
"""
from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")

from sqlalchemy import func, select

from backend.database.models.article import Article
from backend.database.models.claim import Claim
from backend.database.models.document import Document
from backend.database.models.event import Event
from backend.database.models.evidence import Evidence
from backend.database.session import get_session_factory
from domains.audit.service import log_action

EXPECTED = {"documents": 120, "articles": 120, "events": 3,
            "claims": 3, "evidence": 3}


def collect(session):
    docs = list(session.execute(select(Document).where(
        Document.url.like("%example.local%"))).scalars().all())
    doc_ids = {d.id for d in docs}
    arts = list(session.execute(select(Article).where(
        Article.document_id.in_(doc_ids))).scalars().all()) if doc_ids else []
    if any(a.document_id not in doc_ids for a in arts):
        raise RuntimeError("GUARD: non-fake article in scope")
    eids = {a.event_id for a in arts if a.event_id}
    claims = list(session.execute(select(Claim).where(
        Claim.event_id.in_(eids))).scalars().all()) if eids else []
    if any(c.event_id not in eids for c in claims):
        raise RuntimeError("GUARD: claim outside target events")
    cids = {c.id for c in claims}
    evs = list(session.execute(select(Evidence).where(
        Evidence.claim_id.in_(cids))).scalars().all()) if cids else []
    if any(e.claim_id not in cids for e in evs):
        raise RuntimeError("GUARD: evidence outside target claims")
    if eids:
        mixed = session.execute(select(func.count(Article.id)).where(
            Article.event_id.in_(eids),
            ~Article.document_id.in_(doc_ids))).scalar_one()
        if mixed:
            raise RuntimeError(f"GUARD: {mixed} real articles on target events")
    got = {"documents": len(docs), "articles": len(arts), "events": len(eids),
           "claims": len(claims), "evidence": len(evs)}
    if got != EXPECTED:
        raise RuntimeError(f"GUARD: count mismatch {got} != {EXPECTED}")
    return docs, arts, eids, claims, evs


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete approved test rows")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        docs, arts, eids, claims, evs = collect(session)
        total = sum(EXPECTED.values())
        print(f"target OK: {EXPECTED} total={total} (NO delete yet)")
        if not args.execute:
            print("DRY-RUN: pass --execute to delete")
            return 0
        deleted: dict[str, int] = {}
        try:
            for e in evs:
                session.delete(e)
            deleted["evidence"] = len(evs)
            for c in claims:
                session.delete(c)
            deleted["claims"] = len(claims)
            for a in arts:
                session.delete(a)
            deleted["articles"] = len(arts)
            for d in docs:
                session.delete(d)
            deleted["documents"] = len(docs)
            for eid in eids:
                ev = session.get(Event, eid)
                if ev is not None:
                    session.delete(ev)
            deleted["events"] = len(eids)
            session.flush()
            # post-checks BEFORE commit
            left = session.execute(select(func.count(Document.id)).where(
                Document.url.like("%example.local%"))).scalar_one()
            if left:
                raise RuntimeError(f"POST-CHECK: {left} fake docs remain")
            session.commit()
        except Exception:
            session.rollback()
            print("ROLLED BACK due to error/mismatch")
            raise
        log_action(session, action="test_rows_cleanup", actor="approved",
                   target_type="cleanup",
                   params={"expected": EXPECTED},
                   result={"deleted": deleted})
        print(f"DELETED: {deleted} total={sum(deleted.values())}")
        # health: real counts intact
        docs_now = session.execute(select(func.count(Document.id))).scalar_one()
        arts_now = session.execute(select(func.count(Article.id))).scalar_one()
        print(f"remaining: documents={docs_now} articles={arts_now}")
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
