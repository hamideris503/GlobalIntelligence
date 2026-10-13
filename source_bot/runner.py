"""Runner — اجرای یک‌باره/مستمر/تک‌منبع با قفل، retry/backoff، توقف کنترل‌شده."""
from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.document import Document
from backend.database.models.source import Source
from backend.database.session import get_session_factory
from domains.news.fetchers import RawItem
from source_bot.adapters.csv import CsvAdapter
from source_bot.adapters.html import HtmlAdapter
from source_bot.adapters.rest_json import RestJsonAdapter
from source_bot.adapters.rss import BotRSSAdapter
from source_bot.adapters.xml import XmlAdapter
from source_bot.ai_priority_fallback import ai_prioritize
from source_bot.config import get_bot_settings
from source_bot.deduplicator import canonical_url, exact_key
from source_bot.metrics import BotMetrics
from source_bot.output import deliver
from source_bot.priority_engine import score_item
from source_bot.registry import due_sources
from source_bot.validator import validate_source_plan

logger = get_logger(__name__)
LOCK_PATH = os.path.join(tempfile.gettempdir(), "source_bot.lock")
STOP_PATH = os.path.join(tempfile.gettempdir(), "source_bot.stop")


class BotStop(Exception):
    pass


def _acquire_lock() -> bool:
    try:
        fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False


def _release_lock() -> None:
    try:
        os.remove(LOCK_PATH)
    except OSError:
        pass


def should_stop() -> bool:
    return os.path.exists(STOP_PATH) or os.path.exists("/tmp/source_bot.stop")


async def _fetch_plan(plan, settings) -> tuple[list[RawItem], str, dict]:
    """بازگرداندن (items, final_url_note, extra_meta). خطای یک منبع ایزوله است."""
    adapter = plan.adapter
    url = plan.url
    if adapter == "rss":
        items = await BotRSSAdapter(timeout=settings.timeout_seconds).fetch(url=url, limit=20)
        return items, url or "", {}
    if adapter == "rest_json":
        res = await RestJsonAdapter(timeout=settings.timeout_seconds).fetch(url=url, limit=20)
        if res.status == "auth_required":
            return [], url or "", {"source_status": "AUTH_REQUIRED", "detail": res.detail}
        if res.status != "ok":
            raise RuntimeError(res.detail or res.status)
        return res.items, url or "", {}
    if adapter == "csv":
        res = await CsvAdapter(timeout=settings.timeout_seconds).fetch(url=url)
        if res.status == "auth_required":
            return [], url or "", {"source_status": "AUTH_REQUIRED", "detail": res.detail}
        if res.status != "ok":
            raise RuntimeError(res.detail or res.status)
        return res.items, url or "", {}
    if adapter == "xml":
        res = await XmlAdapter(timeout=settings.timeout_seconds).fetch(url=url)
        if res.is_feed:
            items = await BotRSSAdapter(timeout=settings.timeout_seconds).fetch(url=url, limit=20)
            return items, url or "", {"rerouted": "rss"}
        if res.status != "ok":
            raise RuntimeError(res.detail or res.status)
        return res.items, url or "", {}
    if adapter == "html":
        res = await HtmlAdapter(timeout=settings.timeout_seconds).fetch_url(url or "")
        if res.status == "auth_required":
            return [], url or "", {"source_status": "AUTH_REQUIRED", "detail": res.detail}
        if res.status not in ("ok", "empty"):
            raise RuntimeError(res.detail or res.status)
        return res.items, url or "", {}
    return [], url or "", {"source_status": "SKIP", "detail": plan.reason}


async def run_source(db: Session, source: Source, metrics: BotMetrics, settings=None) -> None:
    settings = settings or get_bot_settings()
    from source_bot.registry import pick_adapter as _pick

    plan = _pick(source)
    if plan.adapter == "skip":
        metrics.sources_failed[str(source.name)] = f"skip: {plan.reason}"
        return
    if plan.adapter == "specialized":
        # مالک تخصصی (macro/market) حفظ می‌شود؛ ربات دخالت نمی‌کند
        metrics.sources_checked += 1
        return
    chk = validate_source_plan(plan)
    if not chk.ok:
        metrics.sources_failed[str(source.name)] = chk.reason
        source.last_error = chk.reason[:2000]
        db.commit()
        return
    # retry محدود با backoff فقط برای خطای موقت
    items: list[RawItem] = []
    extra: dict = {}
    last_err = ""
    for attempt in range(settings.max_retries + 1):
        try:
            items, _final, extra = await _fetch_plan(plan, settings)
            last_err = ""
            break
        except Exception as exc:  # noqa: BLE001
            # جزئیات کوتاه و امن (بدون secret؛ آداپتورها فقط نوع/کد خطا می‌سازند)
            last_err = f"{type(exc).__name__}:{str(exc)[:120]}"
            if attempt < settings.max_retries:
                await asyncio.sleep(2.0 * (attempt + 1))
    metrics.sources_checked += 1
    metrics.fetched += len(items)
    if last_err and not items:
        metrics.sources_failed[str(source.name)] = last_err
        source.last_error = last_err[:2000]
        db.commit()
        return
    if extra.get("source_status") == "AUTH_REQUIRED":
        source.last_error = f"AUTH_REQUIRED: {extra.get('detail', '')}"[:2000]
        db.commit()
        metrics.sources_failed[str(source.name)] = "AUTH_REQUIRED"
        return

    seen_keys: set[str] = set()
    for item in items:
        if should_stop():
            raise BotStop
        canon = canonical_url(item.url)
        ext = str((item.metadata or {}).get("external_id") or "") or None
        from domains.news.normalizer import content_hash as _ch
        from domains.news.normalizer import url_hash as _uh

        ch = _ch(item.title, item.raw_text)
        uh = _uh(item.url)
        key = exact_key(ext, canon, ch)
        # تکراری در همین batch (قابل ردیابی در لاگ)
        if key and key in seen_keys:
            metrics.duplicates += 1
            logger.info("duplicate in batch | source=%s key=%s", source.name, key)
            continue
        # تکراری دقیق در DB — همان قرارداد pipeline (درون منبع: url + محتوا)
        exists = None
        if uh and ch:
            exists = db.execute(
                select(Document.id).where(
                    Document.source_id == source.id,
                    Document.hash == uh, Document.content_hash == ch,
                )
            ).first()
        dup_status = "new"
        if exists:
            metrics.duplicates += 1
            dup_status = "exact_duplicate"
            logger.info("duplicate in db | source=%s canonical_id=%s", source.name, exists[0])
            continue
        if key:
            seen_keys.add(key)

        pr = score_item(
            title=item.title, body=item.raw_text,
            source_priority=getattr(source, "priority", None),
            category=getattr(source, "category", None),
            published_at=item.published_at,
            has_author=bool(item.author), settings=settings,
        )
        p_source, p_status = "rules", "RULES_ONLY"
        level, score, conf = pr.level, pr.score, pr.confidence
        if settings.ai_enabled and pr.needs_ai:
            ai = await ai_prioritize(title=item.title, text=item.raw_text,
                                     metadata={"source": source.name})
            if ai is not None and not ai.get("is_mock"):
                metrics.ai_used += 1
                level, conf = ai["priority"], ai["confidence"]
                p_source, p_status = "ai", "AI_DECIDED"
                reason = f"{ai['reason']} [{','.join(ai['reason_codes'])}]"
            else:
                # mock معتبر هم تصمیم واقعی نیست؛ قواعد می‌ماند (صداقت mock)
                metrics.ai_fallback += 1
                p_source = "rules"
                p_status = "RULES_MOCK_AI" if ai is not None else "RULES_FALLBACK_AI_UNAVAILABLE"
                reason = f"rules score={score} [{','.join(pr.reason_codes)}]"
                if conf < 0.3:
                    level, p_status = level, "PRIORITY_PENDING"
        else:
            reason = f"rules score={score} [{','.join(pr.reason_codes)}]"
        try:
            stored = deliver(
                db, source, item, priority=level, score=score, reason=reason,
                priority_source=p_source, priority_status=p_status,
                duplicate_status=dup_status, canonical_url=canon,
                final_url=item.url, external_id=ext,
            )
            if stored:
                metrics.stored += 1
                metrics.by_priority[level] = metrics.by_priority.get(level, 0) + 1
            else:
                metrics.duplicates += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("deliver failed | %s %s", source.name, type(exc).__name__)
    source.last_success = datetime.now(UTC)
    source.last_error = None
    db.commit()
    metrics.sources_ok += 1


async def run_once(*, source_name: str | None = None, limit_sources: int = 50,
                   db: Session | None = None) -> BotMetrics:
    settings = get_bot_settings()
    metrics = BotMetrics()
    if not _acquire_lock():
        raise RuntimeError("another bot run is active (lock exists)")
    try:
        if db is not None:
            await _run_with_db(db, metrics, settings, source_name, limit_sources)
        else:
            SessionLocal = get_session_factory()
            with SessionLocal() as session:
                await _run_with_db(session, metrics, settings, source_name, limit_sources)
    finally:
        _release_lock()
    return metrics


async def _run_with_db(db: Session, metrics: BotMetrics, settings,
                       source_name: str | None, limit_sources: int) -> None:
    if source_name:
        src = db.execute(select(Source).where(Source.name == source_name)).scalar_one_or_none()
        if src is None:
            raise ValueError(f"source not found: {source_name}")
        await run_source(db, src, metrics, settings)
    else:
        for src in due_sources(db, interval_seconds=settings.per_source_interval,
                               limit=limit_sources)[:limit_sources]:
            try:
                await run_source(db, src, metrics, settings)
            except BotStop:
                break
            except Exception as exc:  # noqa: BLE001 — یک منبع کل ربات را متوقف نمی‌کند
                metrics.sources_failed[str(src.name)] = type(exc).__name__


async def run_forever(*, poll_seconds: int = 300) -> None:
    while not should_stop():
        try:
            await run_once()
        except Exception as exc:  # noqa: BLE001
            logger.warning("bot tick failed: %s", type(exc).__name__)
        for _ in range(poll_seconds):
            if should_stop():
                return
            await asyncio.sleep(1)
