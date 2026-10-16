"""Cleanup DRY-RUN preview — فقط SELECT و چاپ برنامه؛ هیچ DELETE/TRUNCATE ندارد.

اجرا:
    python -m scripts.preview_cleanup
کد خروج 0 یعنی برنامه معتبر است (نه اینکه چیزی حذف شده باشد).
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from sqlalchemy import select

from backend.database.models.article import Article
from backend.database.models.claim import Claim
from backend.database.models.document import Document
from backend.database.models.evidence import Evidence
from backend.database.session import get_session_factory

EXPECTED = {"documents": 120, "articles": 120, "events": 3,
            "claims": 3, "evidence": 3}


def main() -> int:
    session = get_session_factory()()
    try:
        docs = list(session.execute(select(Document).where(
            Document.url.like("%example.local%"))).scalars().all())
        doc_ids = {d.id for d in docs}
        arts = list(session.execute(select(Article).where(
            Article.document_id.in_(doc_ids))).scalars().all())
        # guard 1: همه‌ی articleها باید fake باشند
        if any(a.document_id not in doc_ids for a in arts):
            print("ABORT: non-fake article in scope")
            return 2
        eids = {a.event_id for a in arts if a.event_id}
        claims = list(session.execute(select(Claim).where(
            Claim.event_id.in_(eids))).scalars().all()) if eids else []
        if any(c.event_id not in eids for c in claims):
            print("ABORT: claim outside target events")
            return 2
        cids = {c.id for c in claims}
        evs = list(session.execute(select(Evidence).where(
            Evidence.claim_id.in_(cids))).scalars().all()) if cids else []
        if any(e.claim_id not in cids for e in evs):
            print("ABORT: evidence outside target claims")
            return 2
        # guard 2: eventها نباید article واقعی داشته باشند
        if eids:
            from sqlalchemy import func as _func

            mixed = session.execute(select(_func.count(Article.id)).where(
                Article.event_id.in_(eids),
                ~Article.document_id.in_(doc_ids))).scalar_one()
            if mixed:
                print(f"ABORT: {mixed} real articles on target events")
                return 2
        got = {"documents": len(docs), "articles": len(arts),
               "events": len(eids), "claims": len(claims), "evidence": len(evs)}
        print(f"preview: {got} total={sum(got.values())}")
        # guard 3: تطابق دقیق با انتظار
        if got != EXPECTED:
            print(f"ABORT: expected {EXPECTED}")
            return 2
        print("plan (transactional, in order):")
        print("  1. fresh backup + verify restore")
        print("  2. BEGIN; delete evidence(3) -> claims(3) -> articles(120) "
              "-> documents(120) -> events(3), verifying rowcounts")
        print("  3. on any mismatch/exception: ROLLBACK")
        print("  4. post-checks: example.local=0, real counts unchanged, "
              "relationships intact")
        print("  5. audit log entry (deletion record, IDs summarized)")
        print("DRY-RUN OK: nothing deleted")
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
