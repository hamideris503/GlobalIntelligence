"""Runner — اجرای یک‌باره/مستمر/تک‌منبع با قفل، retry/backoff، توقف کنترل‌شده."""
from __future__ import annotations

import asyncio
import os
import tempfile
import time
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.document import Document
from backend.database.models.source import Source
from backend.database.session import get_session_factory
from domains.news.dedup_service import run_post_ingest_dedup
from domains.news.fetchers import RawItem
from source_bot.adapters.csv import CsvAdapter
from source_bot.adapters.html import HtmlAdapter
from source_bot.adapters.rest_json import RestJsonAdapter
from source_bot.adapters.rss import BotRSSAdapter
from source_bot.adapters.xml import XmlAdapter
from source_bot.ai_priority_fallback import ai_prioritize
from source_bot.config import BotConfigError, get_bot_settings
from source_bot.deduplicator import canonical_url, exact_key
from source_bot.fulltext import article_allowlist, enrich_rss_items
from source_bot.metrics import BotMetrics
from source_bot.output import deliver
from source_bot.priority_engine import priority_provenance, score_item
from source_bot.registry import due_sources, endpoint_options
from source_bot.validator import validate_source_plan

logger = get_logger(__name__)
LOCK_PATH = os.path.join(tempfile.gettempdir(), "source_bot.lock")
STOP_PATH = os.path.join(tempfile.gettempdir(), "source_bot.stop")


class BotStop(Exception):
    pass


MAX_ITEMS_PER_SOURCE = 200  # سقف --items؛ هم‌تراز با سقف limit در API


def _validated_items_cap(value: object) -> int | None:
    """None = بدون سقف (رفتار قبلی)؛ وگرنه فقط int در [1, MAX_ITEMS_PER_SOURCE]."""
    if value is None:
        return None
    if (isinstance(value, bool) or not isinstance(value, int)
            or not 1 <= value <= MAX_ITEMS_PER_SOURCE):
        raise ValueError(
            f"max_items_per_source must be an integer within [1, {MAX_ITEMS_PER_SOURCE}]"
        )
    return value


def _lock_owner_pid() -> int | None:
    try:
        with open(LOCK_PATH, encoding="utf-8") as fh:
            return int(fh.read().strip().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def _pid_alive(pid: int) -> bool | None:
    """True: مالک زنده؛ False: قطعاً مرده؛ None: نامشخص (حذف نکن)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            err = kernel32.GetLastError()
            if err == 5:  # ERROR_ACCESS_DENIED: هست ولی دسترسی نداریم
                return True
            if err == 87:  # ERROR_INVALID_PARAMETER: چنین پردازشی نیست
                return False
            return None
        except Exception:  # noqa: BLE001
            return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:  # noqa: BLE001
        return None
    return True


def _acquire_lock() -> bool:
    for _ in range(2):
        try:
            fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            pid = _lock_owner_pid()
            if pid is None or _pid_alive(pid) is not False:
                return False  # مالک زنده یا نامشخص: هرگز تصاحب نکن
            try:
                os.remove(LOCK_PATH)  # فقط stale قطعی؛ بازنده‌ی مسابقه False می‌گیرد
            except OSError:
                return False
    return False


def _release_lock() -> None:
    try:
        os.remove(LOCK_PATH)
    except OSError:
        pass


def should_stop() -> bool:
    return os.path.exists(STOP_PATH) or os.path.exists("/tmp/source_bot.stop")


def _page_cap(opts: dict, settings) -> int:
    """سقف صفحات REST از endpoint_config؛ نامعتبر/غیرمثبت/بزرگ → پیش‌فرض و سقف تنظیمات.

    مقدار نامحدود پذیرفته نمی‌شود: max(1, min(درخواست, BotSettings.max_pages_per_source)).
    """
    try:
        value = int(str(opts.get("max_pages")))
    except (TypeError, ValueError):
        value = 3  # پیش‌فرض قبلی adapter
    if value < 1:
        value = 3
    return max(1, min(value, int(settings.max_pages_per_source)))


async def _fetch_plan(plan, settings) -> tuple[list[RawItem], str, dict]:
    """بازگرداندن (items, final_url_note, extra_meta). خطای یک منبع ایزوله است."""
    adapter = plan.adapter
    url = plan.url
    opts = endpoint_options(plan.source)
    if adapter == "rss":
        items = await BotRSSAdapter(timeout=settings.timeout_seconds,
                                    max_bytes=settings.max_bytes).fetch(url=url, limit=20)
        return items, url or "", {}
    if adapter == "rest_json":
        items_path = opts.get("items_path")
        res = await RestJsonAdapter(timeout=settings.timeout_seconds,
                                    max_bytes=settings.max_bytes,
                                    max_redirects=settings.max_redirects).fetch(
            url=url, limit=20, api_key_env=plan.api_key_env,
            items_path=items_path if isinstance(items_path, str) and items_path.strip() else None,
            max_pages=_page_cap(opts, settings))
        if res.status == "auth_required":
            return [], url or "", {"source_status": "AUTH_REQUIRED", "detail": res.detail}
        if res.status != "ok":
            raise RuntimeError(res.detail or res.status)
        return res.items, url or "", {}
    if adapter == "csv":
        raw_map = opts.get("mapping")
        mapping = ({str(k): str(v) for k, v in raw_map.items()}
                   if isinstance(raw_map, dict) and raw_map else None)
        res = await CsvAdapter(timeout=settings.timeout_seconds,
                               max_bytes=settings.max_csv_bytes).fetch(url=url, mapping=mapping)
        if res.status == "auth_required":
            return [], url or "", {"source_status": "AUTH_REQUIRED", "detail": res.detail}
        if res.status != "ok":
            raise RuntimeError(res.detail or res.status)
        return res.items, url or "", {}
    if adapter == "xml":
        res = await XmlAdapter(timeout=settings.timeout_seconds,
                               max_bytes=settings.max_bytes).fetch(url=url)
        if res.is_feed:
            # همان بایت‌های دانلودشده؛ یک فید از مسیر XML دوباره از شبکه گرفته نمی‌شود
            items = BotRSSAdapter(timeout=settings.timeout_seconds).parse(
                res.content or b"", limit=20)
            return items, url or "", {"rerouted": "rss"}
        if res.status != "ok":
            raise RuntimeError(res.detail or res.status)
        return res.items, url or "", {}
    if adapter == "html":
        from urllib.parse import urlparse as _up2

        html_adapter = HtmlAdapter(timeout=settings.timeout_seconds,
                                   max_bytes=settings.max_bytes,
                                   max_redirects=settings.max_redirects)
        if plan.crawl and url:
            try:
                host = (_up2(url).hostname or "").lower()
                items = await asyncio.to_thread(
                    html_adapter.crawl, start_urls=[url],
                    allowed_domains=[host] if host else [],
                    max_pages=settings.max_pages_per_source,
                    depth=settings.max_depth,
                    concurrency=settings.concurrency,
                    delay=settings.request_delay,
                    retries=settings.max_retries,
                    redirect_max=settings.max_redirects)
                return items, url or "", {"crawled": len(items)}
            except Exception as exc:  # noqa: BLE001 — fallback تک‌صفحه
                logger.warning("bot crawl failed, single-page fallback | %s %s",
                               plan.url, type(exc).__name__)
        res = await html_adapter.fetch_url(url or "")
        if res.status == "auth_required":
            return [], url or "", {"source_status": "AUTH_REQUIRED", "detail": res.detail}
        if res.status not in ("ok", "empty"):
            raise RuntimeError(res.detail or res.status)
        return res.items, url or "", {}
    return [], url or "", {"source_status": "SKIP", "detail": plan.reason}


async def run_source(db: Session, source: Source, metrics: BotMetrics, settings=None, *,
                     max_items_per_source: int | None = None) -> None:
    settings = settings or get_bot_settings()
    if should_stop():  # توقف از پیش درخواست‌شده: هیچ درخواست خارجیای شروع نمی‌شود
        raise BotStop
    sm = metrics.source(source.name)  # آمار همان منبع؛ پیش‌نیاز گزارش روزانهٔ هر منبع
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
        sm.fetch_attempts += 1
        try:
            items, _final, extra = await _fetch_plan(plan, settings)
            last_err = ""
            sm.fetch_ok = True
            break
        except Exception as exc:  # noqa: BLE001
            # جزئیات کوتاه و امن (بدون secret؛ آداپتورها فقط نوع/کد خطا می‌سازند)
            last_err = f"{type(exc).__name__}:{str(exc)[:120]}"
            if attempt < settings.max_retries:
                await asyncio.sleep(2.0 * (attempt + 1))
    metrics.sources_checked += 1
    metrics.fetched += len(items)
    sm.fetched += len(items)
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

    if max_items_per_source is not None and len(items) > max_items_per_source:
        # سقف پردازش: fetched همان خروجی adapter است؛ فقط ورود به dedup/ذخیره محدود می‌شود
        sm.items_skipped_limit = len(items) - max_items_per_source
        metrics.items_skipped_limit += sm.items_skipped_limit
        items = items[:max_items_per_source]

    # متن اصلی مقاله فقط برای آیتم‌های منتخب (پس از سقف)؛ یک GET به هر مقاله و
    # همان HTML به Trafilatura. شکست هر مقاله → همان آیتم با خلاصهٔ RSS می‌ماند.
    if plan.adapter == "rss" and items:
        allow_hosts = article_allowlist(source)
        if allow_hosts:
            try:
                await enrich_rss_items(
                    items, allowed_hosts=allow_hosts,
                    timeout=settings.timeout_seconds, max_bytes=settings.max_bytes,
                    max_redirects=settings.max_redirects, delay=settings.request_delay,
                )
            except Exception as exc:  # noqa: BLE001 — enrichment نباید منبع را از کار بیندازد
                logger.warning("full-text enrichment skipped | source=%s err=%s",
                               source.name, type(exc).__name__)

    seen_keys: set[str] = set()
    for item in items:
        if should_stop():
            raise BotStop
        canon = canonical_url(item.url)
        ext = str((item.metadata or {}).get("external_id") or "") or None
        from domains.news.normalizer import identity_body as _ib
        from domains.news.normalizer import identity_hash as _ih
        from domains.news.normalizer import url_hash as _uh

        ch = _ih(item.title, _ib(item.raw_text, item.metadata), item.raw_payload, item.url)
        uh = _uh(item.url)
        key = exact_key(ext, canon, ch)
        if key is None:
            metrics.duplicates += 1
            sm.rejected_keyless += 1  # بی‌هویت، نه تکراری — جدا شمرده می‌شود
            logger.info("keyless item skipped | source=%s", source.name)
            continue
        # تکراری در همین batch (قابل ردیابی در لاگ)
        if key and key in seen_keys:
            metrics.duplicates += 1
            sm.duplicates += 1
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
            sm.duplicates += 1
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
        level, score = pr.level, pr.score
        ai_meta = None
        if settings.ai_enabled and pr.needs_ai:
            ai = await ai_prioritize(title=item.title, text=item.raw_text,
                                     metadata={"source": source.name})
            sm.record_ai(ai)  # شمارش/مصرف همان فراخوانی برای همین منبع
            if ai is not None and not ai.get("is_mock"):
                metrics.ai_used += 1
                sm.ai_used += 1
                level = ai["priority"]
                p_source, p_status = "ai", "AI_DECIDED"
                ai_meta = ai  # تنها پاسخ معتبر و پذیرفته‌شده به provenance می‌رود
                reason = f"{ai['reason']} [{','.join(ai['reason_codes'])}]"
            else:
                # mock معتبر هم تصمیم واقعی نیست؛ قواعد می‌ماند (صداقت mock).
                # علت عملیاتی (mock/unavailable) حفظ می‌شود؛ «کم‌اطمینانی» فقط در
                # priority_decision_source ثبت می‌شود، نه با بازنویسی وضعیت.
                metrics.ai_fallback += 1
                sm.ai_fallback += 1
                p_source = "rules"
                p_status = "RULES_MOCK_AI" if ai is not None else "RULES_FALLBACK_AI_UNAVAILABLE"
                reason = f"rules score={score} [{','.join(pr.reason_codes)}]"
        else:
            reason = f"rules score={score} [{','.join(pr.reason_codes)}]"
        # امتیاز قواعد دست‌نخورده می‌ماند؛ سطح می‌تواند از AI بیاید (تفاوت در metadata).
        # منشأ تصمیم از confidence نتیجهٔ قواعد مشتق می‌شود، نه از نام وضعیت.
        pmeta = priority_provenance(rules_confidence=pr.confidence, ai=ai_meta)
        try:
            stored = deliver(
                db, source, item, priority=level, score=score, reason=reason,
                priority_source=p_source, priority_status=p_status,
                duplicate_status=dup_status, canonical_url=canon,
                final_url=item.url, external_id=ext, priority_meta=pmeta,
            )
            if stored:
                metrics.stored += 1
                metrics.by_priority[level] = metrics.by_priority.get(level, 0) + 1
                sm.stored += 1
                sm.by_priority[level] = sm.by_priority.get(level, 0) + 1
                if pmeta.get("priority_decision_source") == "pending":
                    sm.pending += 1
            else:
                metrics.duplicates += 1
                sm.duplicates += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("deliver failed | %s %s", source.name, type(exc).__name__)
    source.last_success = datetime.now(UTC)
    source.last_error = None
    db.commit()
    metrics.sources_ok += 1
    sm.ok = True


async def run_once(*, source_name: str | None = None, limit_sources: int = 50,
                   max_items_per_source: int | None = None,
                   db: Session | None = None) -> BotMetrics:
    cap = _validated_items_cap(max_items_per_source)  # ورودی نامعتبر: پیش از قفل و fetch
    settings = get_bot_settings()
    metrics = BotMetrics()
    if not _acquire_lock():
        raise RuntimeError("another bot run is active (lock exists)")
    try:
        if db is not None:
            await _run_with_db(db, metrics, settings, source_name, limit_sources, cap)
        else:
            SessionLocal = get_session_factory()
            with SessionLocal() as session:
                await _run_with_db(session, metrics, settings, source_name, limit_sources, cap)
    finally:
        _release_lock()
    return metrics


async def _timed_run_source(db: Session, source: Source, metrics: BotMetrics, settings,
                            max_items_per_source: int | None = None) -> None:
    """اجرای یک منبع + ثبت مدت واقعی آن (گزارش روزانه به آن نیاز دارد)."""
    started = time.monotonic()
    try:
        await run_source(db, source, metrics, settings,
                         max_items_per_source=max_items_per_source)
    finally:
        metrics.source(source.name).duration_ms = int((time.monotonic() - started) * 1000)


async def _run_with_db(db: Session, metrics: BotMetrics, settings,
                       source_name: str | None, limit_sources: int,
                       max_items_per_source: int | None = None) -> None:
    if source_name:
        src = db.execute(select(Source).where(Source.name == source_name)).scalar_one_or_none()
        if src is None:
            raise ValueError(f"source not found: {source_name}")
        if not src.active:  # انتخاب صریح منبع غیرفعال، پیش از هر درخواست خارجی رد می‌شود
            raise ValueError(f"source is inactive: {source_name}")
        try:
            await _timed_run_source(db, src, metrics, settings, max_items_per_source)
        except BotStop:
            metrics.stopped = True  # آمار جزئی حفظ می‌شود؛ اجرا کامل نیست
    else:
        for src in due_sources(db, interval_seconds=settings.per_source_interval,
                               limit=limit_sources)[:limit_sources]:
            try:
                await _timed_run_source(db, src, metrics, settings, max_items_per_source)
            except BotStop:
                metrics.stopped = True
                break
            except Exception as exc:  # noqa: BLE001 — یک منبع کل ربات را متوقف نمی‌کند
                metrics.sources_failed[str(src.name)] = type(exc).__name__
    # dedup پس از ingest — دقیقاً یک بار به‌ازای هر اجرا (نه هر منبع/آیتم) و فقط
    # وقتی سندی تازه ذخیره شده باشد؛ همان قرارداد مسیر pipeline. خطا فقط لاگ می‌شود.
    # بعد از توقف هم اجرا می‌شود: محلی است، سندی حذف نمی‌کند و فقط خوشه‌بندی می‌کند.
    run_post_ingest_dedup(db, stored=metrics.stored)


async def run_forever(*, poll_seconds: int = 300) -> None:
    while not should_stop():
        try:
            await run_once()
        except BotConfigError as exc:  # پیکربندی ثابت نامعتبر است؛ چرخه بی‌پایان بی‌فایده
            logger.error("bot stopped: invalid priority configuration | %s", exc)
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("bot tick failed: %s", type(exc).__name__)
        for _ in range(poll_seconds):
            if should_stop():
                return
            await asyncio.sleep(1)
