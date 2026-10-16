"""Registry — خواندن منابع از جدول Source موجود؛ بدون جدول موازی."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.source import Source

_API_KEY_ENV_RE = re.compile(r"[A-Z][A-Z0-9_]{0,63}")


@dataclass
class SourcePlan:
    source: Source
    adapter: str  # rss | rest_json | csv | xml | html | market | macro | skip
    url: str | None
    reason: str = ""
    api_key_env: str | None = None  # فقط نام متغیر محیطی؛ مقدار هرگز ذخیره نمی‌شود
    crawl: bool = False  # html چندصفحه‌ای (opt-in صریح هر منبع)


def _opt(source: Source, name: str) -> str | None:
    """خواندن دفاعی فیلدهای اختیاری مدل Source.

    مدل‌های قدیمی‌تر (بدون ستون‌های census) این ویژگی‌ها را ندارند؛
    به‌جای AttributeError، None برمی‌گردد و منطق انتخاب بدون تغییر می‌ماند.
    """
    return getattr(source, name, None)


def _api_key_env(source: Source) -> str | None:
    """نام متغیر محیطی کلید از endpoint_config همان منبع (JSON).

    فقط نام خوانده می‌شود؛ مقدار secret فقط در runtime از environment.
    قالب نامعتبر/غیرمنتظره نادیده گرفته می‌شود (رفتار بدون کلید).
    """
    try:
        cfg = json.loads(_opt(source, "endpoint_config") or "")
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(cfg, dict):
        return None
    name = cfg.get("api_key_env")
    if isinstance(name, str) and _API_KEY_ENV_RE.fullmatch(name.strip()):
        return name.strip()
    return None


def _wants_crawl(source: Source) -> bool:
    """crawl چندصفحه‌ای فقط با opt-in صریح همان منبع."""
    try:
        cfg = json.loads(_opt(source, "endpoint_config") or "")
    except Exception:  # noqa: BLE001
        return False
    return isinstance(cfg, dict) and cfg.get("crawl") is True


def _api_endpoint(source: Source) -> str:
    """URL مستقیم api یا api_url داخل endpoint_config همان منبع."""
    direct = _opt(source, "api_url") or ""
    if direct.strip():
        return direct.strip()
    try:
        cfg = json.loads(_opt(source, "endpoint_config") or "")
    except Exception:  # noqa: BLE001
        return ""
    url = cfg.get("api_url") if isinstance(cfg, dict) else None
    return url.strip() if isinstance(url, str) and url.strip() else ""


def pick_adapter(source: Source) -> SourcePlan:
    method = (source.collection_method or "").lower()
    stype = (source.type or "").lower()
    feed = source.feed_url or _opt(source, "rss_url")
    api = _api_endpoint(source)
    if method == "rss" or (feed and stype in ("rss", "", "other")):
        if not feed:
            return SourcePlan(source, "skip", None, "rss method but no feed url")
        return SourcePlan(source, "rss", feed, "rss feed")
    if method == "api" or api:
        if api:
            return SourcePlan(source, "rest_json", api, "api endpoint",
                              api_key_env=_api_key_env(source))
        # BLS case: متد api ولی بدون api_url؛ feed ثبت‌شده → RSS.
        # مالکیت تخصصی محفوظ است: منابع macro/market بدون feed همچنان specialized.
        if feed:
            return SourcePlan(source, "rss", feed, "fallback rss (no api_url)")
        return SourcePlan(source, "specialized", None,
                          "kept: macro/market specialized fetcher owns this source (no generic api_url)")
    data_url = _opt(source, "data_download_url") or ""
    if method == "dataset" or data_url:
        url = data_url
        if not url:
            return SourcePlan(source, "specialized", None,
                              "kept: dataset fetched by specialized engine (no download url registered)")
        if url.lower().endswith(".csv"):
            return SourcePlan(source, "csv", url, "dataset csv")
        return SourcePlan(source, "xml", url, "dataset xml")
    homepage = _opt(source, "homepage_url")
    if method == "scrape" or homepage:
        if not homepage:
            return SourcePlan(source, "skip", None, "scrape needs homepage_url before crawl")
        return SourcePlan(source, "html", homepage, "scrape homepage",
                           crawl=_wants_crawl(source))
    if feed:
        return SourcePlan(source, "rss", feed, "fallback rss")
    return SourcePlan(source, "skip", None, "no usable endpoint")


def due_sources(db: Session, *, interval_seconds: int = 3600, limit: int = 50) -> list[Source]:
    stmt = select(Source).where(Source.active.is_(True)).limit(limit)
    sources = list(db.execute(stmt).scalars().all())
    now = datetime.now(UTC)
    out = []
    for s in sources:
        last = s.last_success
        if last is None:
            out.append(s)
            continue
        try:
            if last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            if (now - last).total_seconds() >= interval_seconds:
                out.append(s)
        except Exception:  # noqa: BLE001
            out.append(s)
    return out
