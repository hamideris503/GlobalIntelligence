"""Configuration Control Plane API (F03.0).

- GET  /api/configuration/definitions               → قرارداد descriptor
- GET  /api/configuration/definitions/{kind}
- GET  /api/configuration/instances?kind=
- POST /api/configuration/instances                 → instance + revision 1 (draft)
- GET  /api/configuration/instances/{id}            → instance + تاریخچه
- POST /api/configuration/instances/{id}/revisions  → revision جدید (optimistic lock)
- POST /api/configuration/instances/{id}/revisions/{n}/validate
- POST /api/configuration/instances/{id}/revisions/{n}/test      (بدون ingest)
- POST /api/configuration/instances/{id}/revisions/{n}/activate
- POST /api/configuration/instances/{id}/rollback                (revision جدید)

احراز هویت از include_router در main می‌آید. هیچ کلید/secret در پاسخ نیست.
"""
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.schemas.configuration import (
    ActivateRequest,
    InstanceCreate,
    InstanceDetail,
    InstanceRead,
    RevisionCreate,
    RevisionRead,
    RevisionResult,
    RollbackRequest,
    TestRequest,
)
from backend.configuration import descriptors, service
from backend.configuration.errors import ConfigurationError
from backend.database.models.configuration import ConfigurationInstance, ConfigurationRevision
from backend.database.session import get_db

router = APIRouter(prefix="/api/configuration", tags=["configuration"])

ACTIVE = service.STATUS_ACTIVE


def _http(exc: ConfigurationError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=str(exc))


def _load(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except Exception:  # noqa: BLE001
        return None
    return value if isinstance(value, dict) else None


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="bad id") from exc


def _revision_read(row: ConfigurationRevision, kind: str) -> RevisionRead:
    payload = _load(row.payload_json) or {}
    return RevisionRead(
        id=str(row.id),
        instance_id=str(row.instance_id),
        revision_number=row.revision_number,
        status=row.status,
        payload=descriptors.redact(kind, payload),
        validation=_load(row.validation_json),
        test=_load(row.test_json),
        descriptor_version=row.descriptor_version,
        actor=row.actor,
        note=row.note,
        created_at=row.created_at,
        activated_at=row.activated_at,
    )


def _instance_read(
    db: Session, row: ConfigurationInstance, *, with_revisions: bool = False
) -> InstanceRead:
    active = service.active_revision(db, row)
    base = dict(
        id=str(row.id),
        kind=row.kind,
        slug=row.slug,
        latest_revision=row.latest_revision,
        active_revision=row.active_revision,
        active_status=ACTIVE if active is not None else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )
    if not with_revisions:
        return InstanceRead(**base)
    return InstanceDetail(
        **base,
        revisions=[_revision_read(r, row.kind) for r in service.list_revisions(db, row)],
    )


@router.get("/definitions")
def list_definitions() -> list[dict]:
    return descriptors.all_definitions()


@router.get("/definitions/{kind}")
def get_definition(kind: str) -> dict:
    try:
        return descriptors.definition(kind).as_dict()
    except ConfigurationError as exc:
        raise _http(exc) from exc


@router.get("/instances")
def list_instances(
    kind: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
) -> list[InstanceRead]:
    return [_instance_read(db, row) for row in service.list_instances(db, kind=kind)]


@router.post("/instances")
def create_instance(payload: InstanceCreate, db: Session = Depends(get_db)) -> InstanceDetail:
    try:
        instance, revision = service.create_instance(
            db,
            kind=payload.kind,
            slug=payload.slug,
            payload=payload.payload,
            note=payload.note,
        )
    except ConfigurationError as exc:
        raise _http(exc) from exc
    return InstanceDetail(
        **_instance_read(db, instance).model_dump(),
        revisions=[_revision_read(revision, instance.kind)],
    )


@router.get("/instances/{instance_id}")
def get_instance(instance_id: str, db: Session = Depends(get_db)) -> InstanceDetail:
    try:
        instance = service.instance_or_404(db, _uuid(instance_id))
    except ConfigurationError as exc:
        raise _http(exc) from exc
    return _instance_read(db, instance, with_revisions=True)


@router.post("/instances/{instance_id}/revisions")
def create_revision(
    instance_id: str, payload: RevisionCreate, db: Session = Depends(get_db)
) -> RevisionRead:
    try:
        revision = service.create_revision(
            db,
            _uuid(instance_id),
            payload=payload.payload,
            expected_revision=payload.expected_revision,
            note=payload.note,
        )
    except ConfigurationError as exc:
        raise _http(exc) from exc
    return _revision_read(revision, _kind_of(db, revision))


def _kind_of(db: Session, revision: ConfigurationRevision) -> str:
    instance = db.get(ConfigurationInstance, revision.instance_id)
    return instance.kind if instance is not None else ""


@router.post("/instances/{instance_id}/revisions/{number}/validate")
def validate_revision(
    instance_id: str, number: int, db: Session = Depends(get_db)
) -> RevisionResult:
    try:
        revision, result = service.validate_revision(db, _uuid(instance_id), number)
    except ConfigurationError as exc:
        raise _http(exc) from exc
    return RevisionResult(
        revision=_revision_read(revision, _kind_of(db, revision)), result=result
    )


@router.post("/instances/{instance_id}/revisions/{number}/test")
def test_revision(
    instance_id: str,
    number: int,
    payload: TestRequest | None = None,
    db: Session = Depends(get_db),
) -> RevisionResult:
    body = payload or TestRequest()
    try:
        revision, result = service.test_revision(
            db, _uuid(instance_id), number, limit=body.limit
        )
    except ConfigurationError as exc:
        raise _http(exc) from exc
    return RevisionResult(
        revision=_revision_read(revision, _kind_of(db, revision)), result=result
    )


@router.post("/instances/{instance_id}/revisions/{number}/activate")
def activate_revision(
    instance_id: str,
    number: int,
    payload: ActivateRequest,
    db: Session = Depends(get_db),
) -> RevisionRead:
    try:
        revision = service.activate_revision(
            db, _uuid(instance_id), number, expected_revision=payload.expected_revision
        )
    except ConfigurationError as exc:
        raise _http(exc) from exc
    return _revision_read(revision, _kind_of(db, revision))


@router.post("/instances/{instance_id}/rollback")
def rollback_instance(
    instance_id: str, payload: RollbackRequest, db: Session = Depends(get_db)
) -> RevisionRead:
    try:
        revision = service.rollback(
            db,
            _uuid(instance_id),
            target_revision=payload.target_revision,
            expected_revision=payload.expected_revision,
            note=payload.note,
        )
    except ConfigurationError as exc:
        raise _http(exc) from exc
    return _revision_read(revision, _kind_of(db, revision))
