"""Adaptive AI Router API (Phase 37).

- POST /api/ai-routing/record  → ثبت نتیجه‌ی یک اجرای task
- GET  /api/ai-routing/stats   → آمار هر (task, provider)
- GET  /api/ai-routing/routes  → زنجیره‌ی تطبیقی پیشنهادی
- POST /api/ai-routing/apply   → اعمال زنجیره‌ها روی gateway در runtime
"""
from __future__ import annotations

from domains.ai_routing.router import AdaptiveRouter
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ai.gateway import get_gateway
from backend.database.models.provider_run_stat import ProviderRunStat
from backend.database.session import get_db

router = APIRouter(prefix="/api/ai-routing", tags=["ai-routing"])


class RunRecordRequest(BaseModel):
    task: str
    provider: str
    model: str
    success: bool = True
    latency_ms: float | None = None
    structured_ok: bool = False
    period: str | None = None


class RunRecordRead(BaseModel):
    provider: str
    model: str
    task: str
    period: str
    calls: int
    successes: int
    failures: int


class StatRead(BaseModel):
    task: str
    provider: str
    model: str
    period: str
    calls: int
    successes: int
    failures: int
    success_rate: float


@router.post("/record", response_model=RunRecordRead)
def record_run(req: RunRecordRequest, db: Session = Depends(get_db)) -> RunRecordRead:
    """ثبت نتیجه‌ی یک اجرای task توسط یک Provider."""
    if not req.task.strip() or not req.provider.strip() or not req.model.strip():
        raise HTTPException(status_code=422, detail="task/provider/model required")
    row = AdaptiveRouter(db).record(
        task=req.task.strip(),
        provider=req.provider.strip(),
        model=req.model.strip(),
        success=req.success,
        latency_ms=req.latency_ms,
        structured_ok=req.structured_ok,
        period=req.period,
    )
    return RunRecordRead(
        provider=row.provider,
        model=row.model,
        task=row.task,
        period=row.period,
        calls=row.calls or 0,
        successes=row.successes or 0,
        failures=row.failures or 0,
    )


@router.get("/stats", response_model=list[StatRead])
def stats(
    task: str | None = None,
    limit: int = Query(default=200, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> list[StatRead]:
    stmt = (
        select(ProviderRunStat)
        .order_by(
            ProviderRunStat.task, ProviderRunStat.period.desc(), ProviderRunStat.provider
        )
        .limit(limit)
    )
    if task:
        stmt = stmt.where(ProviderRunStat.task == task)
    out = []
    for r in db.execute(stmt).scalars().all():
        calls = r.calls or 0
        out.append(
            StatRead(
                task=r.task,
                provider=r.provider,
                model=r.model,
                period=r.period,
                calls=calls,
                successes=r.successes or 0,
                failures=r.failures or 0,
                success_rate=round((r.successes or 0) / calls, 4) if calls else 0.0,
            )
        )
    return out


@router.get("/routes")
def routes(
    tasks: list[str] | None = Query(default=None), db: Session = Depends(get_db)
) -> dict:
    """زنجیره‌ی تطبیقی پیشنهادی برای taskها (بدون اعمال)."""
    router_ = AdaptiveRouter(db)
    return {
        task: router_.suggest(task=task).as_dict()
        for task in (tasks or ["classify_article", "extract_relations"])
    }


@router.post("/apply")
def apply_routes(
    tasks: list[str] | None = Query(default=None), db: Session = Depends(get_db)
) -> dict:
    """اعمال زنجیره‌های تطبیقی روی gateway در runtime."""
    router_ = AdaptiveRouter(db)
    routes = router_.build_routes(tasks or ["classify_article", "extract_relations"])
    get_gateway().set_routes(routes)
    return {"applied": True, "tasks": sorted(routes)}
