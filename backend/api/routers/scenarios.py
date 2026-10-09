"""Scenario Engine API (Phase 30).

- POST /api/scenarios/run → ساخت ۴ سناریو برای یک هدف
- GET  /api/scenarios       → آخرین مجموعه‌ی سناریو هر هدف
"""
from __future__ import annotations

from domains.scenarios.engine import ScenarioEngine
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.forecast import Forecast
from backend.database.session import get_db

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])

SCENARIO_ORDER = ["base", "bull", "bear", "tail"]


class ScenarioOutcomeRead(BaseModel):
    created: int
    skipped: int
    failed: int
    superseded: int
    forecast_ids: list[str]
    scenarios: dict[str, float]
    errors: list[str]


class ScenarioSetRead(BaseModel):
    target: str
    scenarios: dict[str, float | None]
    forecast_ids: dict[str, str]


@router.post("/run", response_model=ScenarioOutcomeRead)
def run_scenarios(
    target: str = Query(...),
    method: str = Query(default="naive"),
    horizon: str = Query(default="short"),
    db: Session = Depends(get_db),
) -> ScenarioOutcomeRead:
    """ساخت ۴ سناریو برای یک هدف (base/bull/bear/tail)."""
    outcome = ScenarioEngine(db).run(target=target, method=method, horizon=horizon)
    return ScenarioOutcomeRead(**outcome.as_dict())


@router.get("", response_model=list[ScenarioSetRead])
def list_scenario_sets(
    target: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ScenarioSetRead]:
    """آخرین مجموعه‌ی سناریو هر هدف (فقط وضعیت active)."""
    stmt = (
        select(Forecast)
        .where(Forecast.scenario.is_not(None), Forecast.status == "active")
        .order_by(Forecast.target, Forecast.scenario, Forecast.created_at.desc())
    )
    if target:
        stmt = stmt.where(Forecast.target == target)
    grouped: dict[str, dict[str, Forecast]] = {}
    for fc in db.execute(stmt).scalars().all():
        bucket = grouped.setdefault(fc.target or "", {})
        if fc.scenario in SCENARIO_ORDER and fc.scenario not in bucket:
            bucket[fc.scenario] = fc
    out: list[ScenarioSetRead] = []
    for tgt, bucket in sorted(grouped.items()):
        if len(out) >= limit:
            break
        out.append(
            ScenarioSetRead(
                target=tgt,
                scenarios={k: bucket[k].expected_value for k in SCENARIO_ORDER if k in bucket},
                forecast_ids={k: str(bucket[k].id) for k in SCENARIO_ORDER if k in bucket},
            )
        )
    return out
