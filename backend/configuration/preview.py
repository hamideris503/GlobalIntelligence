"""Non-ingesting preview (F03.0 — الزام ۲.۶).

قرارداد: این ماژول **هیچ** رکوردی در DB نمی‌نویسد، هیچ counter دریافت را
تغییر نمی‌دهد و فایل خام را ذخیره نمی‌کند. فقط:
1. سیاست اتصال (`connection_check`: scheme، userinfo، DNS و IP عمومی) اجرا می‌شود.
2. همان adapter رجیستری برای fetch/parse صدا زده می‌شود.
3. نمونه‌های پاک‌سازی‌شده (بدون متن کامل، بدون کوئری URL) برگردانده می‌شود.
"""
from __future__ import annotations

import asyncio
import hashlib

from source_bot.registry import PREVIEW_ADAPTERS
from source_bot.security import connection_check, url_origin

MAX_TITLE_CHARS = 200
MAX_SUMMARY_CHARS = 280


class PreviewError(Exception):
    """پیش‌نمایش ممکن نشد (URL رد شد یا fetch شکست خورد)."""


class UnsupportedAdapter(PreviewError):
    """این adapter قابلیت preview ندارد؛ صادقانه گزارش می‌شود."""


def _text(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def preview_fetch(adapter: str, url: str | None, limit: int = 5) -> dict:
    """fetch + parse بدون ingest؛ خروجی sanitized و قابل‌ثبت به‌عنوان شاهد تست."""
    if adapter not in PREVIEW_ADAPTERS:
        raise UnsupportedAdapter(
            f"preview is not supported for adapter '{adapter}'; "
            f"supported: {list(PREVIEW_ADAPTERS)}"
        )
    if not url:
        raise PreviewError("no url to preview")
    check = connection_check(url)
    if not check.ok:
        raise PreviewError(f"url rejected by connection policy: {check.reason}")

    from source_bot.adapters.rss import BotRSSAdapter

    try:
        items = asyncio.run(BotRSSAdapter().fetch(url=url, limit=max(1, limit)))
    except Exception as exc:  # noqa: BLE001 - نوع خطا کافی است، پیام خام لو نمی‌رود
        raise PreviewError(f"fetch failed: {type(exc).__name__}") from exc

    samples = []
    for item in items[: max(1, limit)]:
        body = _text(getattr(item, "content", None), 10_000)
        summary = _text(getattr(item, "summary", None), MAX_SUMMARY_CHARS)
        published = getattr(item, "published_at", None)
        samples.append(
            {
                "title": _text(getattr(item, "title", None), MAX_TITLE_CHARS),
                "summary": summary or None,
                "content_chars": len(body),
                "content_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest()[:16],
                "published_at": published.isoformat() if hasattr(published, "isoformat") else None,
            }
        )
    return {
        "adapter": adapter,
        "url_origin": url_origin(url) or None,
        "count": len(samples),
        "samples": samples,
        "ingested": False,
    }


__all__ = [
    "MAX_SUMMARY_CHARS",
    "MAX_TITLE_CHARS",
    "PreviewError",
    "UnsupportedAdapter",
    "preview_fetch",
]
