"""Archive management API (F13)."""
from __future__ import annotations

import os
from typing import Any

from domains.archive.catalog import get_archive, list_archives
from domains.archive.restore import restore_dry_run, restore_from_zip
from domains.archive.service import (
    archive_settings,
    check_zip_security,
    measure_storage,
    purge_candidates,
    validate_archive_zip,
)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database.session import get_db

router = APIRouter(prefix="/api/archive", tags=["archive"])


@router.get("/storage")
def storage(db: Session = Depends(get_db)) -> dict[str, Any]:
    return measure_storage(db)


@router.get("/settings")
def settings() -> dict[str, Any]:
    return archive_settings()


@router.get("/catalog")
def catalog(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    rows = list_archives(db)
    return [
        {
            "archive_id": r.archive_id,
            "batch_id": r.batch_id,
            "parent_batch_id": r.parent_batch_id,
            "part_index": r.part_index,
            "total_parts": r.total_parts,
            "file_name": r.file_name,
            "file_size": r.file_size,
            "sha256": r.sha256,
            "validation_status": r.validation_status,
            "restore_status": r.restore_status,
            "telegram_status": r.telegram_status,
            "article_count": r.article_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/catalog/{archive_id}")
def catalog_item(archive_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    r = get_archive(db, archive_id)
    if r is None:
        raise HTTPException(status_code=404, detail="archive not found")
    return {
        "archive_id": r.archive_id,
        "batch_id": r.batch_id,
        "parent_batch_id": r.parent_batch_id,
        "part_index": r.part_index,
        "total_parts": r.total_parts,
        "file_name": r.file_name,
        "file_size": r.file_size,
        "sha256": r.sha256,
        "archive_path": r.archive_path,
        "validation_status": r.validation_status,
        "restore_status": r.restore_status,
        "telegram_status": r.telegram_status,
        "article_count": r.article_count,
        "record_counts_json": r.record_counts_json,
        "manifest_json": r.manifest_json,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.post("/validate")
def validate(payload: dict[str, Any]) -> dict[str, Any]:
    path = payload.get("path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="file not found")
    sec_ok, sec_errors = check_zip_security(path)
    v = validate_archive_zip(path)
    return {"security_ok": sec_ok, "security_errors": sec_errors, "validation": v}


@router.post("/restore/dry-run")
def restore_dry(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    path = payload.get("path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="file not found")
    return restore_dry_run(db, path)


@router.post("/restore")
def restore(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    path = payload.get("path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="file not found")
    dry = bool(payload.get("dry_run", False))
    return restore_from_zip(db, path, dry_run=dry)


@router.get("/purge/preview")
def purge_preview(db: Session = Depends(get_db)) -> dict[str, Any]:
    # Dry-run only: never deletes.
    cands = purge_candidates(db)
    return {"auto_purge_enabled": archive_settings()["ARCHIVE_AUTO_PURGE_ENABLED"],
            "purge_dry_run": archive_settings()["PURGE_DRY_RUN"],
            "candidate_count": len(cands),
            "candidates": cands}


@router.post("/telegram/{archive_id}")
def telegram_send(archive_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from domains.archive.telegram import send_archive_to_telegram

    r = get_archive(db, archive_id)
    if r is None:
        raise HTTPException(status_code=404, detail="archive not found")
    enabled = os.getenv("TELEGRAM_ARCHIVE_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")
    if not enabled:
        return {"ok": False, "status": "disabled", "detail": "TELEGRAM_ARCHIVE_ENABLED is false"}
    if not (os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")):
        r.telegram_status = "pending_credentials"
        db.commit()
        return {"ok": False, "status": "pending_credentials", "detail": "Bot token not configured"}
    return send_archive_to_telegram(db, archive_id)
