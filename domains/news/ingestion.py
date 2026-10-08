"""News Ingestion pipeline (Phase 8; اصلاحات Phase 10 fix).

مسیر: SOURCE → FETCH → RAW DOCUMENT → NORMALIZE → DATABASE

اصلاحات مهم:
- داده‌ی خام اصلی (`raw_payload`) و متن پاک‌شده (`raw_text`) هر دو ذخیره می‌شوند (بند 19).
- **همه‌ی** اسناد منبع‌های مختلف ذخیره می‌شوند؛ یکتایی فقط درون یک منبع است
  (بند 18: تفاوت mention و تأیید مستقل).
- هر آیتم در یک savepoint ذخیره می‌شود تا خطای یک آیتم بقیه را خراب نکند.
- فقط منابع RSS با feed_url معتبر دریافت می‌شوند.
- موفقیت/خطای منبع ثبت می‌شود (last_success/last_error).
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news.fetchers import BaseFetcher, MockFetcher, RawItem, RSSFetcher
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
    return RSSFetcher(
        timeout=float(settings.ai_request_timeout_seconds),
        user_agent=settings.user_agent,
    )


def _feed_url(source: Source) -> str | None:
    """آدرس فید واقعی منبع. در MOCK_MODE می‌تواند None باشد."""
    return source.feed_url


class NewsIngestionPipeline:
    def __init__(self, db: Session, fetcher: BaseFetcher | None = None) -> None:
        self.db = db
        self.fetcher = fetcher or select_fetcher()

    # --- ذخیره‌سازی ---
    def store_item(self, source: Source, item: RawItem) -> bool:
        """آیتم را normalize و ذخیره می‌کند.

        Returns:
            True اگر سند جدید ذخیره شد، False اگر تکراری درون همین منبع بود.
        """
        norm = normalize(item)

        # یکتایی فقط درون یک منبع (بند 18)
        exists = self.db.execute(
            select(Document.id).where(
                Document.source_id == source.id,
                Document.hash == norm.hash,
                Document.content_hash == norm.content_hash,
            )
        ).first()
        if exists:
            return False

        # revision: اگر همان URL با محتوای متفاوت آمده باشد
        revision = 1
        if norm.hash:
            prev = self.db.execute(
                select(Document.revision)
                .where(Document.source_id == source.id, Document.hash == norm.hash)
                .order_by(Document.revision.desc().nullslast())
                .limit(1)
            ).scalar_one_or_none()
            if prev:
                revision = int(prev) + 1

        doc = Document(
            source_id=source.id,
            url=norm.url,
            title=norm.title,
            raw_payload=norm.raw_payload,
            raw_text=norm.raw_text,
            language=norm.language,
            author=norm.author,
            revision=revision,
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
                summary=None,  # خلاصه‌ی واقعی در Phase 10 ساخته می‌شود
                language=norm.language,
                source_name=source.name,
                published_at=norm.published_at,
                retrieved_at=norm.retrieved_at,
                available_at=norm.available_at,
                observed_at=norm.observed_at,
                classification_status="pending",
            )
        )
        return True

    def _record(self, result: IngestionResult, source: Source, items: list[RawItem]) -> None:
        result.fetched = len(items)
        for item in items:
            # savepoint: خطای یک آیتم بقیه را خراب نکند (P1-12)
            try:
                with self.db.begin_nested():
                    stored = self.store_item(source, item)
                if stored:
                    result.stored += 1
                else:
                    result.duplicates += 1
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"store failed: {type(exc).__name__}: {exc}")
                logger.warning("store_item failed | source=%s err=%s", source.name, exc)
        self.db.commit()

        if get_settings().dedup_on_ingest and result.stored:
            try:
                from domains.news.dedup_service import DedupService

                DedupService(self.db).run(limit=get_settings().dedup_window)
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"dedup failed: {type(exc).__name__}: {exc}")

    def _mark_source(self, source: Source, ok: bool, error: str | None = None) -> None:
        from datetime import datetime

        if ok:
            source.last_success = datetime.now(UTC)
            source.last_error = None
        else:
            source.last_error = (error or "unknown error")[:2000]
        self.db.commit()

    # --- مسیر async (API) ---
    async def ingest_source_async(self, source: Source, *, limit: int = 20) -> IngestionResult:
        result = IngestionResult(source_name=source.name)
        try:
            items = await self.fetcher.fetch(url=_feed_url(source), limit=limit)
        except Exception as exc:  # noqa: BLE001
            msg = f"{type(exc).__name__}: {exc}"
            result.errors.append(f"fetch failed: {msg}")
            self._mark_source(source, ok=False, error=msg)
            logger.warning("ingest fetch failed | source=%s err=%s", source.name, exc)
            return result
        self._record(result, source, items)
        self._mark_source(source, ok=not result.errors or result.stored > 0)
        logger.info("ingest done | %s", result.as_dict())
        return result

    # --- مسیر sync (worker/CLI) ---
    def ingest_source(self, source: Source, *, limit: int = 20) -> IngestionResult:
        return asyncio.run(self.ingest_source_async(source, limit=limit))
