"""Dedup service — اجرای خوشه‌بندی روی Documentهای ذخیره‌شده و ثبت نتیجه (Phase 9).

نتیجه در `Document.doc_metadata` (JSON) به‌عنوان dedup_cluster ذخیره می‌شود و
روی `Article.duplicate_cluster` نیز بازتاب می‌یابد.
"""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.article import Article
from backend.database.models.document import Document
from domains.news.dedup import DedupInput, DedupResult, cluster_documents

logger = get_logger(__name__)


class DedupService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _load_inputs(self, *, limit: int, source_id=None) -> list[tuple[Document, DedupInput]]:
        stmt = select(Document).order_by(Document.retrieved_at.desc().nullslast()).limit(limit)
        if source_id is not None:
            stmt = stmt.where(Document.source_id == source_id)
        docs = list(self.db.execute(stmt).scalars().all())
        inputs = []
        for d in docs:
            text = f"{d.title or ''}. {d.raw_text or ''}".strip()
            src_name = d.source.name if d.source else None
            inputs.append(
                (
                    d,
                    DedupInput(
                        id=str(d.id),
                        text=text,
                        content_hash=d.content_hash,
                        source_name=src_name,
                    ),
                )
            )
        return inputs

    def run(self, *, limit: int = 500, source_id=None, near_threshold: float | None = None) -> dict:
        from backend.core.config import get_settings

        threshold = (
            near_threshold
            if near_threshold is not None
            else get_settings().dedup_near_threshold
        )
        pairs_list = self._load_inputs(limit=limit, source_id=source_id)
        docs_by_id = {str(d.id): d for d, _ in pairs_list}
        result: DedupResult = cluster_documents(
            [inp for _, inp in pairs_list], near_threshold=threshold
        )

        # تعداد اعضای هر خوشه برای نام‌گذاری
        updated = 0
        for doc_id, root in result.cluster_of.items():
            doc = docs_by_id.get(doc_id)
            if doc is None:
                continue
            members = result.clusters.get(root, [doc_id])
            # فقط اسنادی که در خوشه‌ی چندنفره‌اند مقدار می‌گیرند
            cluster_value = root if len(members) > 1 else None
            meta = {}
            if doc.doc_metadata:
                try:
                    meta = json.loads(doc.doc_metadata)
                except Exception:  # noqa: BLE001
                    meta = {}
            meta["dedup_cluster"] = cluster_value
            doc.doc_metadata = json.dumps(meta, ensure_ascii=False)
            updated += 1

            # بازتاب روی Article
            for art in self.db.execute(
                select(Article).where(Article.document_id == doc.id)
            ).scalars().all():
                art.duplicate_cluster = cluster_value

        self.db.commit()

        duplicate_clusters = {k: v for k, v in result.clusters.items() if len(v) > 1}
        summary = {
            "documents": len(pairs_list),
            "clusters_total": len(result.clusters),
            "duplicate_clusters": len(duplicate_clusters),
            "exact_pairs": sum(1 for p in result.pairs if p.kind == "exact"),
            "near_pairs": sum(1 for p in result.pairs if p.kind == "near"),
            "repost_pairs": sum(1 for p in result.pairs if p.kind == "repost"),
            "updated": updated,
        }
        logger.info("dedup done | %s", summary)
        return summary
