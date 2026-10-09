"""Audit service — ثبت لاگ اقدام (Phase 38).

لاگ افزودنی است؛ هیچ رکوردی ویرایش/حذف نمی‌شود.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.audit_record import AuditRecord

logger = get_logger(__name__)


def log_action(
    db: Session,
    *,
    action: str,
    actor: str = "api",
    target_type: str | None = None,
    target_id: str | None = None,
    params: dict | None = None,
    result: dict | None = None,
    status: str = "ok",
) -> AuditRecord:
    """ثبت یک اقدام در لاگ حسابرسی."""
    record = AuditRecord(
        action=action,
        actor=actor,
        target_type=target_type,
        target_id=target_id,
        params=json.dumps(params or {}, ensure_ascii=False),
        result=json.dumps(result or {}, ensure_ascii=False),
        status=status,
        observed_at=datetime.now(UTC),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    logger.info("audit | action=%s actor=%s status=%s", action, actor, status)
    return record


__all__ = ["log_action"]
