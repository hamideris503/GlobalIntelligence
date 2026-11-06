"""Runtime configuration pinning (بند ۲.۷).

منبع حقیقت: `ConfigurationInstance(kind="source", slug=<Source.name>)`.
اگر revision فعالی برای همان منبع وجود داشته باشد، runtime **همان payload** را
پین می‌کند و adapter از آن انتخاب می‌شود؛ ردیف `Source` فقط fallback است.

قواعد:
- pin فقط وقتی اعمال می‌شود که revision وضعیت `active` داشته باشد.
- اگر payload پین‌شده به `skip` برسد (پیکربندی ناقص)، به ردیف زنده برمی‌گردیم و
  revision گزارش‌شده `None` است — هرگز اجرا با پیکربندی ناقص متوقف نمی‌شود.
- خطای DB/جدول غایب، اجرای دریافت را نمی‌شکند (fallback + لاگ هشدار).
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from source_bot.registry import SourcePlan, pick_adapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.configuration import ConfigurationInstance, ConfigurationRevision

logger = get_logger(__name__)

KIND_SOURCE = "source"


def pinned_payload(db: Session, source_name: str) -> tuple[int | None, dict | None]:
    """(revision_number, payload) برای revision فعال منبع؛ در غیر این صورت (None, None)."""
    try:
        instance = db.execute(
            select(ConfigurationInstance).where(
                ConfigurationInstance.kind == KIND_SOURCE,
                ConfigurationInstance.slug == str(source_name),
            )
        ).scalars().first()
        if instance is None or instance.active_revision is None:
            return None, None
        revision = db.execute(
            select(ConfigurationRevision).where(
                ConfigurationRevision.instance_id == instance.id,
                ConfigurationRevision.revision_number == instance.active_revision,
                ConfigurationRevision.status == "active",
            )
        ).scalars().first()
        if revision is None:
            return None, None
        payload = json.loads(revision.payload_json)
        if not isinstance(payload, dict):
            return None, None
        return revision.revision_number, payload
    except Exception as exc:  # noqa: BLE001 — بدون DB باید زنده بماند
        logger.warning(
            "config pin lookup skipped | source=%s err=%s", source_name, type(exc).__name__
        )
        return None, None


def plan_from_payload(payload: dict, source) -> SourcePlan:  # noqa: ANN001
    """ساخت plan از payload پین‌شده با همان `pick_adapter` رجیستری."""
    cfg = payload.get("endpoint_config")
    source_like = SimpleNamespace(
        name=payload.get("name") or getattr(source, "name", ""),
        type=payload.get("type") or getattr(source, "type", None) or "other",
        collection_method=payload.get("collection_method") or "",
        feed_url=payload.get("feed_url"),
        rss_url=payload.get("rss_url"),
        api_url=payload.get("api_url"),
        homepage_url=payload.get("homepage_url"),
        data_download_url=payload.get("data_download_url"),
        endpoint_config=(
            json.dumps(cfg, ensure_ascii=False) if isinstance(cfg, dict) else None
        ),
        priority=getattr(source, "priority", None),
        category=payload.get("category") or getattr(source, "category", None),
    )
    return pick_adapter(source_like)


def resolve_source_plan(db: Session, source) -> tuple[SourcePlan, int | None]:  # noqa: ANN001
    """(plan, pinned_revision): پین معتبر بر ردیف زنده اولویت دارد."""
    number, payload = pinned_payload(db, source.name)
    if number is not None and payload is not None:
        plan = plan_from_payload(payload, source)
        if plan.adapter != "skip":
            return plan, number
        logger.warning(
            "pinned config unusable, falling back to live row | source=%s rev=%s",
            source.name,
            number,
        )
    return pick_adapter(source), None


__all__ = ["KIND_SOURCE", "pinned_payload", "plan_from_payload", "resolve_source_plan"]
