"""Registry — خواندن منابع از جدول Source موجود؛ بدون جدول موازی."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.source import Source


@dataclass
class SourcePlan:
    source: Source
    adapter: str  # rss | rest_json | csv | xml | html | market | macro | skip
    url: str | None
    reason: str = ""


def _opt(source: Source, name: str) -> str | None:
    """خواندن دفاعی فیلدهای اختیاری مدل Source.

    مدل‌های قدیمی‌تر (بدون ستون‌های census) این ویژگی‌ها را ندارند؛
    به‌جای AttributeError، None برمی‌گردد و منطق انتخاب بدون تغییر می‌ماند.
    """
    return getattr(source, name, None)


def pick_adapter(source: Source) -> SourcePlan:
    method = (source.collection_method or "").lower()
    stype = (source.type or "").lower()
    feed = source.feed_url or _opt(source, "rss_url")
    api = _opt(source, "api_url") or (_opt(source, "endpoint_config") or "")
    if method == "rss" or (feed and stype in ("rss", "", "other")):
        if not feed:
            return SourcePlan(source, "skip", None, "rss method but no feed url")
        return SourcePlan(source, "rss", feed, "rss feed")
    if method == "api" or api:
        api_url = _opt(source, "api_url")
        if api_url:
            return SourcePlan(source, "rest_json", api_url, "api endpoint")
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
        return SourcePlan(source, "html", homepage, "scrape homepage")
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
