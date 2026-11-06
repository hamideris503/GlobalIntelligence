"""Configuration revision lifecycle (F03.0 — الزام ۲.۲ و ۲.۵).

قواعد:
- تاریخچه افزودنی است: هیچ revision ویرایش یا حذف نمی‌شود.
- `latest_revision` نسخهٔ instance است؛ هر نوشتن باید `expected_revision` برابر
  آن بفرستد وگرنه 409 (optimistic locking).
- گذار مجاز: draft → validated → tested → active → archived.
- revision فعال تغییرناپذیر است؛ تغییر بعدی یک revision جدید می‌سازد.
- rollback هم یک revision جدید می‌سازد (کپی payload هدف) تا تاریخچه گم نشود.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from domains.audit.service import log_action
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.configuration import descriptors
from backend.configuration.errors import Conflict, Invalid, NotFound
from backend.configuration.preview import PreviewError, UnsupportedAdapter, preview_fetch
from backend.database.models.configuration import ConfigurationInstance, ConfigurationRevision

STATUS_DRAFT = "draft"
STATUS_VALIDATED = "validated"
STATUS_TESTED = "tested"
STATUS_ACTIVE = "active"
STATUS_ARCHIVED = "archived"

STATUSES = (STATUS_DRAFT, STATUS_VALIDATED, STATUS_TESTED, STATUS_ACTIVE, STATUS_ARCHIVED)


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except Exception:  # noqa: BLE001
        return None
    return value if isinstance(value, dict) else None


def instance_or_404(db: Session, instance_id: uuid.UUID) -> ConfigurationInstance:
    row = db.get(ConfigurationInstance, instance_id)
    if row is None:
        raise NotFound("configuration instance not found")
    return row


def revision_or_404(
    db: Session, instance: ConfigurationInstance, number: int
) -> ConfigurationRevision:
    row = db.execute(
        select(ConfigurationRevision).where(
            ConfigurationRevision.instance_id == instance.id,
            ConfigurationRevision.revision_number == number,
        )
    ).scalars().first()
    if row is None:
        raise NotFound(f"revision {number} not found")
    return row


def _append_revision(
    db: Session,
    instance: ConfigurationInstance,
    payload: dict,
    *,
    actor: str,
    note: str | None = None,
) -> ConfigurationRevision:
    number = instance.latest_revision + 1
    instance.latest_revision = number
    row = ConfigurationRevision(
        instance_id=instance.id,
        revision_number=number,
        status=STATUS_DRAFT,
        payload_json=_dump(payload),
        descriptor_version=descriptors.DESCRIPTOR_VERSION,
        actor=actor,
        note=(note or "").strip() or None,
    )
    db.add(row)
    db.flush()
    return row


def create_instance(
    db: Session,
    *,
    kind: str,
    slug: str,
    payload: dict,
    actor: str = "api",
    note: str | None = None,
) -> tuple[ConfigurationInstance, ConfigurationRevision]:
    descriptors.definition(kind)
    if not slug.strip():
        raise Invalid("slug is required")
    exists = db.execute(
        select(ConfigurationInstance).where(
            ConfigurationInstance.kind == kind, ConfigurationInstance.slug == slug.strip()
        )
    ).scalars().first()
    if exists is not None:
        raise Conflict("configuration instance already exists")
    instance = ConfigurationInstance(kind=kind, slug=slug.strip(), latest_revision=0)
    db.add(instance)
    db.flush()
    revision = _append_revision(db, instance, payload, actor=actor, note=note)
    db.commit()
    db.refresh(instance)
    db.refresh(revision)
    return instance, revision


def create_revision(
    db: Session,
    instance_id: uuid.UUID,
    *,
    payload: dict,
    expected_revision: int,
    actor: str = "api",
    note: str | None = None,
) -> ConfigurationRevision:
    instance = instance_or_404(db, instance_id)
    if expected_revision != instance.latest_revision:
        raise Conflict(
            f"stale revision: expected {expected_revision}, current {instance.latest_revision}"
        )
    revision = _append_revision(db, instance, payload, actor=actor, note=note)
    db.commit()
    db.refresh(instance)
    db.refresh(revision)
    return revision


def validate_revision(
    db: Session, instance_id: uuid.UUID, number: int
) -> tuple[ConfigurationRevision, dict]:
    instance = instance_or_404(db, instance_id)
    revision = revision_or_404(db, instance, number)
    if revision.status in (STATUS_ACTIVE, STATUS_ARCHIVED):
        raise Conflict(f"revision {number} is immutable ({revision.status})")
    result = descriptors.validate(instance.kind, _load(revision.payload_json) or {})
    revision.validation_json = _dump(result)
    revision.status = STATUS_VALIDATED if result["ok"] else STATUS_DRAFT
    db.commit()
    db.refresh(revision)
    return revision, result


def test_revision(
    db: Session, instance_id: uuid.UUID, number: int, *, limit: int = 5
) -> tuple[ConfigurationRevision, dict]:
    instance = instance_or_404(db, instance_id)
    revision = revision_or_404(db, instance, number)
    if revision.status != STATUS_VALIDATED:
        raise Conflict(f"revision {number} must be validated before test ({revision.status})")
    payload = _load(revision.payload_json) or {}
    plan = descriptors.resolve_adapter(payload)
    try:
        result = preview_fetch(plan["adapter"], plan["url"], limit)
    except UnsupportedAdapter as exc:
        # نتیجهٔ ناموفق هم به‌عنوان شاهد ثبت می‌شود؛ هیچ نوشتن دیگری رخ نمی‌دهد.
        revision.test_json = _dump({"ok": False, "reason": "unsupported_adapter",
                                    "adapter": plan["adapter"]})
        db.commit()
        raise Invalid(str(exc)) from exc
    except PreviewError as exc:
        revision.test_json = _dump({"ok": False, "reason": "preview_failed",
                                    "adapter": plan["adapter"]})
        db.commit()
        raise Invalid(str(exc)) from exc
    result = {**result, "ok": True, "tested_at": datetime.now(UTC).isoformat()}
    revision.test_json = _dump(result)
    revision.status = STATUS_TESTED
    db.commit()
    db.refresh(revision)
    return revision, result


def _archive_active(
    db: Session, instance: ConfigurationInstance, keep_id: uuid.UUID | None
) -> None:
    active = db.execute(
        select(ConfigurationRevision).where(
            ConfigurationRevision.instance_id == instance.id,
            ConfigurationRevision.status == STATUS_ACTIVE,
        )
    ).scalars().all()
    for row in active:
        if keep_id is None or row.id != keep_id:
            row.status = STATUS_ARCHIVED


def activate_revision(
    db: Session,
    instance_id: uuid.UUID,
    number: int,
    *,
    expected_revision: int,
    actor: str = "api",
) -> ConfigurationRevision:
    instance = instance_or_404(db, instance_id)
    if expected_revision != instance.latest_revision:
        raise Conflict(
            f"stale revision: expected {expected_revision}, current {instance.latest_revision}"
        )
    revision = revision_or_404(db, instance, number)
    if revision.status != STATUS_TESTED:
        raise Conflict(f"revision {number} must be tested before activate ({revision.status})")
    _archive_active(db, instance, keep_id=revision.id)
    revision.status = STATUS_ACTIVE
    revision.activated_at = datetime.now(UTC)
    instance.active_revision = revision.revision_number
    db.commit()
    db.refresh(revision)
    log_action(
        db,
        action="configuration_activate",
        actor=actor,
        target_type="configuration_instance",
        target_id=str(instance.id),
        params={"kind": instance.kind, "slug": instance.slug, "revision": revision.revision_number},
        result={"ok": True},
    )
    return revision


def rollback(
    db: Session,
    instance_id: uuid.UUID,
    *,
    target_revision: int,
    expected_revision: int,
    actor: str = "api",
    note: str | None = None,
) -> ConfigurationRevision:
    """بازگردانی با revision جدید (تاریخچه پاک نمی‌شود).

    validation دوباره اجرا می‌شود (قطعی و بدون شبکه)؛ تست شبکه دوباره اجرا نمی‌شود
    و شاهد قبلی به‌صورت `inherited_from` ثبت می‌گردد.
    """
    instance = instance_or_404(db, instance_id)
    if expected_revision != instance.latest_revision:
        raise Conflict(
            f"stale revision: expected {expected_revision}, current {instance.latest_revision}"
        )
    target = revision_or_404(db, instance, target_revision)
    payload = _load(target.payload_json)
    if payload is None:
        raise Invalid(f"revision {target_revision} has no usable payload")
    new_revision = _append_revision(
        db, instance, payload, actor=actor,
        note=note or f"rollback to r{target_revision}",
    )
    result = descriptors.validate(instance.kind, payload)
    new_revision.validation_json = _dump(result)
    if not result["ok"]:
        db.commit()
        raise Invalid(f"revision {target_revision} no longer validates")
    new_revision.test_json = _dump(
        {"ok": True, "inherited_from": target_revision, "network_test_skipped": True}
    )
    new_revision.status = STATUS_TESTED
    _archive_active(db, instance, keep_id=None)
    new_revision.status = STATUS_ACTIVE
    new_revision.activated_at = datetime.now(UTC)
    instance.active_revision = new_revision.revision_number
    db.commit()
    db.refresh(new_revision)
    log_action(
        db,
        action="configuration_rollback",
        actor=actor,
        target_type="configuration_instance",
        target_id=str(instance.id),
        params={"kind": instance.kind, "slug": instance.slug, "target": target_revision},
        result={"revision": new_revision.revision_number},
    )
    return new_revision


def active_revision(
    db: Session, instance: ConfigurationInstance
) -> ConfigurationRevision | None:
    return db.execute(
        select(ConfigurationRevision).where(
            ConfigurationRevision.instance_id == instance.id,
            ConfigurationRevision.status == STATUS_ACTIVE,
        )
    ).scalars().first()


def list_revisions(
    db: Session, instance: ConfigurationInstance
) -> list[ConfigurationRevision]:
    return list(
        db.execute(
            select(ConfigurationRevision)
            .where(ConfigurationRevision.instance_id == instance.id)
            .order_by(ConfigurationRevision.revision_number)
        ).scalars().all()
    )


def list_instances(
    db: Session, *, kind: str | None = None
) -> list[ConfigurationInstance]:
    stmt = select(ConfigurationInstance).order_by(
        ConfigurationInstance.kind, ConfigurationInstance.slug
    )
    if kind:
        stmt = stmt.where(ConfigurationInstance.kind == kind)
    return list(db.execute(stmt).scalars().all())


__all__ = [
    "STATUSES",
    "STATUS_ACTIVE",
    "STATUS_ARCHIVED",
    "STATUS_DRAFT",
    "STATUS_TESTED",
    "STATUS_VALIDATED",
    "activate_revision",
    "active_revision",
    "create_instance",
    "create_revision",
    "instance_or_404",
    "list_instances",
    "list_revisions",
    "revision_or_404",
    "rollback",
    "test_revision",
    "validate_revision",
]
