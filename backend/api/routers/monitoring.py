"""Production Monitoring API (Phase 50).

- GET /api/ops/monitoring → گزارش چک‌های مانیتورینگ + وضعیت کلی
- GET /api/ops/metrics     → متریک‌ها به فرمت Prometheus exposition
"""
from __future__ import annotations

from domains.ops.service import MonitoringService
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.session import get_db

router = APIRouter(prefix="/api/ops", tags=["ops"])


class MonitoringOutcomeRead(BaseModel):
    status: str
    checks: list[dict]


@router.get("/monitoring", response_model=MonitoringOutcomeRead)
def monitoring_report(db: Session = Depends(get_db)) -> MonitoringOutcomeRead:
    """گزارش مانیتورینگ production (فقط‌خواندنی)."""
    outcome = MonitoringService(db).report()
    return MonitoringOutcomeRead(**outcome.as_dict())


@router.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics(db: Session = Depends(get_db)) -> str:
    """متریک‌ها به فرمت Prometheus (برای scrape خارجی)."""
    return MonitoringService(db).prometheus()
