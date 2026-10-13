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


def pick_adapter(source: Source) -> SourcePlan:
    method = (source.collection_method or "").lower()
    stype = (source.type or "").lower()
    feed = source.feed_url or source.rss_url
    api = source.api_url or (source.endpoint_config or "")
    if method == "rss" or (feed and stype in ("rss", "", "other")):
        if not feed:
            return SourcePlan(source, "skip", None, "rss method but no feed url")
        return SourcePlan(source, "rss", feed, "rss feed")
    if method == "api" or api:
        if not source.api_url:
            return SourcePlan(source, "specialized", None,
                              "kept: macro/market specialized fetcher owns this source (no generic api_url)")
        return SourcePlan(source, "rest_json", source.api_url, "api endpoint")
    if method == "dataset" or source.data_download_url:
        url = source.data_download_url or ""
        if not url:
            return SourcePlan(source, "specialized", None,
                              "kept: dataset fetched by specialized engine (no download url registered)")
        if url.lower().endswith(".csv"):
            return SourcePlan(source, "csv", url, "dataset csv")
        return SourcePlan(source, "xml", url, "dataset xml")
    if method == "scrape" or source.homepage_url:
        if not source.homepage_url:
            return SourcePlan(source, "skip", None, "scrape needs homepage_url before crawl")
        return SourcePlan(source, "html", source.homepage_url, "scrape homepage")
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
