"""News Ingestion pipeline (Phase 8; اصلاحات Phase 10 fix).

مسیر: SOURCE → FETCH → RAW DOCUMENT → NORMALIZE → DATABASE

اصلاحات مهم:
- داده‌ی خام اصلی (`raw_payload`) و متن پاک‌شده (`raw_text`) هر دو ذخیره می‌شوند (بند 19).
- **همه‌ی** اسناد منبع‌های مختلف ذخیره می‌شوند؛ یکتایی فقط درون یک منبع است
  (بند 18: تفاوت mention و تأیید مستقل).
- ردیف بدون URL هویت اعلام‌شده دارد: (source_id, external_id) با index یکتای جزئی؛
  نقض هم‌زمان همان = duplicate (بدون تغییر رکورد موجود).
- هر آیتم در یک savepoint ذخیره می‌شود تا خطای یک آیتم بقیه را خراب نکند.
- فقط منابع RSS با feed_url معتبر دریافت می‌شوند.
- موفقیت/خطای منبع ثبت می‌شود (last_success/last_error).
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.database.models.article import Article
from backend.database.models.document import _RIDLESS_CONTENT_WHERE, Document
from backend.database.models.source import Source
from domains.news.fetchers import BaseFetcher, MockFetcher, RawItem, RSSFetcher
from domains.news.normalizer import NormalizedItem, deterministic_summary, normalize
from source_bot.config import BotConfigError, get_bot_settings  # preflight پیکربندی اولویت
from source_bot.priority_engine import UNRELIABLE_CONFIDENCE  # تک‌منبع آستانهٔ اطمینان قواعد

logger = get_logger(__name__)


def _apply_deterministic_priority(doc: Document, source: Source, norm: NormalizedItem) -> None:
    """اولویت قطعی P0..P4 روی سند تازه‌ساخته‌ی مسیرهای عادی ingestion.

    همان موتور `source_bot.priority_engine` صدا زده می‌شود (منطق موازی نمی‌سازیم).
    اگر آیتم از قبل تصمیم معتبر دارد (مسیر source_bot آن را در metadata گذاشته و
    خودش ستون‌ها را می‌نویسد)، دست نمی‌زنیم.
    """
    from source_bot.priority_engine import LEVELS, priority_provenance, score_item  # lazy

    meta = norm.metadata or {}
    if str(meta.get("ingestion_priority") or "").strip().upper() in LEVELS:
        return
    pr = score_item(
        title=norm.title,
        body=norm.raw_text,
        source_priority=getattr(source, "priority", None),
        category=getattr(source, "category", None),
        published_at=norm.published_at,
        has_author=bool(norm.author),
    )
    doc.ingestion_priority = pr.level
    doc.priority_score = pr.score
    doc.priority_reason = f"rules score={pr.score} [{','.join(pr.reason_codes)}]"
    doc.priority_source = "rules"
    doc.priority_status = (
        "PRIORITY_PENDING" if pr.confidence < UNRELIABLE_CONFIDENCE else "RULES_ONLY"
    )
    # همان قرارداد metadata مسیر Source Bot (بدون بازنویسی کلیدهای موجود)
    from source_bot.output import merge_priority_metadata  # lazy: چرخهٔ import

    doc.doc_metadata = merge_priority_metadata(
        doc.doc_metadata,
        priority_provenance(rules_confidence=pr.confidence),
    )


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
    """انتخاب fetcher بر اساس حالت Mock مؤثر (بند 72-73)."""
    from backend.core.mock_mode import effective_mock_mode

    settings = get_settings()
    if effective_mock_mode():
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

        # منشأ نامعلوم صریح علامت می‌خورد (بدون حدس real/mock) تا هیچ مسیر تازه‌ای
        # خاموش provenance نداشته باشد. این کلید در هویت خبر دخیل نیست (هویت فقط از
        # identity_text/title/URL/payload می‌آید)، پس hash و content_hash و dedup
        # دست‌نخورده می‌مانند و ingestion هم متوقف نمی‌شود.
        if isinstance(norm.metadata, dict) and "mock" not in norm.metadata:
            norm.metadata["provenance_missing"] = True
            logger.warning("provenance missing | source=%s adapter=%s",
                           source.name, norm.metadata.get("adapter"))

        # یکتایی فقط درون یک منبع (بند 18).
        # ردیف بدون URL (سری زمانی CSV/ردیف API بدون لینک) هویت محتوایی ندارد:
        # عنوان مشترک دو دوره را ادغام می‌کرد و بدون عنوان هم اولین ردیف همه را
        # می‌بلعید. برای این ردیف‌ها هویت اعلام‌شده‌ی آداپتور (external_id) کلید است
        # — همان ترتیبی که `source_bot.deduplicator.exact_key` استفاده می‌کند.
        # ردیف‌های URL‌دار دست‌نخورده‌اند (revision و dedup قبلی حفظ می‌شود).
        ext_id = None
        if norm.hash is None:
            ext_id = str((norm.metadata or {}).get("external_id") or "").strip() or None
        if norm.hash is None and norm.content_hash is None and ext_id is None:
            # بدون URL/عنوان/متن/payload/external_id هیچ هویتی وجود ندارد؛
            # جست‌وجوی NULL/NULL این ردیف را بی‌صدا با هر ردیف بی‌هویت دیگری
            # ادغام می‌کرد. ردیف خام حفظ می‌شود (قرارداد فعلی) اما بی‌هویت
            # اعلام می‌شود و در dedup شرکت نمی‌کند.
            logger.warning("identity-less item: no dedup identity | source=%s", source.name)
            exists = None
        elif ext_id:
            exists = self._has_external_id(source, ext_id)
        else:
            exists = self._identity_exists(source, norm)
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

        # خلاصهٔ قطعی از متن پاک‌شده؛ شکست آن نباید سند خام را از دست بدهد.
        try:
            summary = deterministic_summary(norm.raw_text)
        except Exception as exc:  # noqa: BLE001 — همان الگوی محافظ priority
            logger.warning("summary failed | source=%s err=%s", source.name, type(exc).__name__)
            summary = None

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
            external_id=ext_id,  # هویت اعلام‌شده‌ی ردیف بدون URL (وگرنه None)
            doc_metadata=json.dumps(norm.metadata, ensure_ascii=False, default=str),
        )
        try:
            _apply_deterministic_priority(doc, source, norm)
        except Exception as exc:  # noqa: BLE001 — شکست اولویت‌بندی نباید سند خام را حذف کند
            logger.warning("priority scoring failed | source=%s err=%s", source.name,
                           type(exc).__name__)
        try:
            # savepoint: نقض یکتایی فقط این درج را برمی‌گرداند (نه کل batch).
            # `add` داخل savepoint است: `begin_nested()` پیش از بازکردن savepoint
            # flush می‌کند و اگر Insert بیرون آن بیفتد نقض قید کل تراکنش را باطل
            # می‌کند (بازیابی duplicate غیرممکن و کل batch از دست می‌رود).
            with self.db.begin_nested():
                self.db.add(doc)
                self.db.flush()
                self.db.add(
                    Article(
                        document_id=doc.id,
                        title=norm.title,
                        summary=summary,  # خلاصهٔ قطعی محلی (بدون AI)؛ classifier در صورت وجود خلاصهٔ AI جایگزین می‌کند
                        language=norm.language,
                        source_name=source.name,
                        published_at=norm.published_at,
                        retrieved_at=norm.retrieved_at,
                        available_at=norm.available_at,
                        observed_at=norm.observed_at,
                        classification_status="pending",
                    )
                )
        except IntegrityError:
            # نقض قید هویت = duplicate (بدون شمارش موفقیت کاذب):
            # - (source_id, external_id) برای ردیف بدون URL؛
            # - (source_id, hash, content_hash) برای ردیف URL‌دار؛
            # - (source_id, content_hash) برای محتوای بدون URL (index جزئی Phase 59).
            # rollback به savepoint خودش شیء (و Article آن) را از session برداشته،
            # پس Article یتیم نمی‌ماند. خطای غیرهویتی بالا می‌رود (نه duplicate پنهان).
            if ext_id and self._has_external_id(source, ext_id):
                return False
            if norm.content_hash and self._ridless_content_exists(source, norm.content_hash):
                return False
            raise
        return True

    def _identity_exists(self, source: Source, norm: NormalizedItem) -> bool:
        """پیش‌بررسی: ردیفی با همان (source_id, hash, content_hash) هست؟ (بدون نوشتن)"""
        return self.db.execute(
            select(Document.id).where(
                Document.source_id == source.id,
                Document.hash == norm.hash,
                Document.content_hash == norm.content_hash,
            )
        ).first() is not None

    def _ridless_content_exists(self, source: Source, content_hash: str) -> bool:
        """ردیف با همان هویت محتوای بدون URL — دقیقاً predicate همان index جزئی."""
        return self.db.execute(
            select(Document.id).where(
                Document.source_id == source.id,
                text(_RIDLESS_CONTENT_WHERE),
                Document.content_hash == content_hash,
            )
        ).first() is not None

    def _has_external_id(self, source: Source, ext_id: str) -> bool:
        """آیا ردیفی با همین هویت اعلام‌شده در همین منبع هست؟ (بدون نوشتن)"""
        return self.db.execute(
            select(Document.id)
            .where(Document.source_id == source.id, Document.external_id == ext_id)
            .limit(1)
        ).first() is not None

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

        # dedup پس از ingest — همین منطق برای Source Bot هم استفاده می‌شود
        from domains.news.dedup_service import run_post_ingest_dedup

        err = run_post_ingest_dedup(self.db, stored=result.stored)
        if err:
            result.errors.append(err)

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
        # preflight: پیکربندی نامعتبر اولویت پیش از هر fetch/ذخیره متوقف می‌کند؛ وگرنه
        # همان خطا در `store_item` گرفته می‌شد و سند با priority=NULL ذخیره می‌شد.
        try:
            get_bot_settings()
        except BotConfigError as exc:
            msg = f"priority configuration invalid: {exc}"
            result.errors.append(msg)
            self._mark_source(source, ok=False, error=msg)
            logger.error("ingest blocked | source=%s | %s", source.name, msg)
            return result
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
