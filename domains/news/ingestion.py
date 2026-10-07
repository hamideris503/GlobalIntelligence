"""News Ingestion pipeline (Phase 8).

مسیر: SOURCE → FETCH → RAW DOCUMENT → NORMALIZE → DATABASE

- داده‌ی خام *قبل* از هر تبدیل ذخیره می‌شود (بند 19: raw layer).
- Document ذخیره می‌شود و یک Article پایه هم ساخته می‌شود تا مسیر کامل باشد.
- dedup سبک بر اساس content_hash (تشخیص کامل در Phase 9).
- هم مسیر async (برای API) و هم مسیر sync (برای worker/CLI) دارد.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news.fetchers import BaseFetcher, MockFetcher, RSSFetcher, RawItem
from domains.news.normalizer import normalize

logger = get_logger(__name__)


@dataclass
class IngestionResult:
    source_name: str
    fetched: int = 0
    stored: int = 0
    duplicates: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "source_name": self.source_name,
            "fetched": self.fetched,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "errors": self.errors,
        }


def select_fetcher() -> BaseFetcher:
    """انتخاب fetcher بر اساس MOCK_MODE (بند 72-73)."""
    settings = get_settings()
    if settings.mock_mode:
        return MockFetcher()
    return RSSFetcher(timeout=settings.ai_request_timeout_seconds)


def _feed_url(source: Source) -> str | None:
    return f"https://{source.domain}/rss" if source.domain else None


class NewsIngestionPipeline:
    def __init__(self, db: Session, fetcher: BaseFetcher | None = None) -> None:
        self.db = db
        self.fetcher = fetcher or select_fetcher()

    # --- ذخیره‌سازی ---
    def store_item(self, source: Source, item: RawItem) -> bool:
        """آیتم را normalize و ذخیره می‌کند. تکراری → False."""
        norm = normalize(item)

        if norm.content_hash:
            dup = self.db.execute(
                select(Document.id).where(Document.content_hash == norm.content_hash)
            ).first()
            if dup:
                return False

        doc = Document(
            source_id=source.id,
            url=norm.url,
            title=norm.title,
            raw_text=norm.raw_text,
            language=norm.language,
            author=norm.author,
            published_at=norm.published_at,
            retrieved_at=norm.retrieved_at,
            available_at=norm.available_at,
            observed_at=norm.observed_at,
            hash=norm.hash,
            content_hash=norm.content_hash,
            license=source.license,
            doc_metadata=json.dumps(norm.metadata, ensure_ascii=False, default=str),
        )
        self.db.add(doc)
        self.db.flush()

        self.db.add(
            Article(
                document_id=doc.id,
                title=norm.title,
                summary=norm.raw_text[:500] if norm.raw_text else None,
                language=norm.language,
                source_name=source.name,
                published_at=norm.published_at,
                retrieved_at=norm.retrieved_at,
                available_at=norm.available_at,
                observed_at=norm.observed_at,
                duplicate_cluster=norm.content_hash,
            )
        )
        return True

    def _record(self, result: IngestionResult, source: Source, items: list[RawItem]) -> None:
        result.fetched = len(items)
        for item in items:
            try:
                if self.store_item(source, item):
                    result.stored += 1
                else:
                    result.duplicates += 1
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"store failed: {type(exc).__name__}: {exc}")
        self.db.commit()

    # --- مسیر async (API) ---
    async def ingest_source_async(self, source: Source, *, limit: int = 20) -> IngestionResult:
        result = IngestionResult(source_name=source.name)
        try:
            items = await self.fetcher.fetch(url=_feed_url(source), limit=limit)
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"fetch failed: {type(exc).__name__}: {exc}")
            logger.warning("ingest fetch failed | source=%s err=%s", source.name, exc)
            return result
        self._record(result, source, items)
        logger.info("ingest done | %s", result.as_dict())
        return result

    # --- مسیر sync (worker/CLI) ---
    def ingest_source(self, source: Source, *, limit: int = 20) -> IngestionResult:
        return asyncio.run(self.ingest_source_async(source, limit=limit))
