"""Retention & Disk Monitoring API (Stage 100).

- GET  /api/retention/dry-run  → dry-run candidate report (no deletion)
- GET  /api/retention/disk     → disk status + alert flag
"""

from __future__ import annotations

from domains.retention import RetentionService, disk_status
from fastapi import APIRouter, Depends

from backend.database.session import get_db

router = APIRouter(prefix="/api/retention", tags=["retention"])


@router.get("/dry-run")
def retention_dry_run(db=Depends(get_db)) -> dict:
    return RetentionService(db).dry_run().as_dict()


@router.get("/disk")
def retention_disk() -> dict:
    st = disk_status()
    return {"disk": st, "alert_needed": st.get("used_percent", 0) >= 70.0}