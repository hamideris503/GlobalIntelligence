"""Forecast Tournament API (Phase 29).

- POST /api/tournaments/run → اجرای تورنمنت و ذخیره‌ی جدول امتیازات
- GET  /api/tournaments       → لیست تورنمنت‌ها
- GET  /api/tournaments/{id}  → یک تورنمنت با leaderboard
"""
from __future__ import annotations

import json
import uuid

from domains.forecast.tournament import TournamentEngine
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.tournament import Tournament
from backend.database.session import get_db

router = APIRouter(prefix="/api/tournaments", tags=["tournaments"])


class TournamentRunRequest(BaseModel):
    targets: list[str]
    methods: list[str] | None = None
    horizon: str = "short"
    scenario: str = "base"
    name: str | None = None


class TournamentOutcomeRead(BaseModel):
    tournament_id: str
    name: str
    board: list[dict]
    winner_model: str | None
    n_forecasts: int


class TournamentRead(BaseModel):
    id: str
    name: str
    targets: list[str]
    methods: list[str]
    horizon: str | None
    board: list[dict]
    winner_model: str | None
    n_forecasts: int | None
    observed_at: str | None


def _parse_list(raw: str | None) -> list:
    try:
        out = json.loads(raw or "[]")
        return out if isinstance(out, list) else []
    except Exception:  # noqa: BLE001
        return []


def _to_tournament(t: Tournament) -> TournamentRead:
    return TournamentRead(
        id=str(t.id),
        name=t.name,
        targets=_parse_list(t.targets),
        methods=_parse_list(t.methods),
        horizon=t.horizon,
        board=_parse_list(t.results),
        winner_model=t.winner_model,
        n_forecasts=t.n_forecasts,
        observed_at=t.observed_at.isoformat() if t.observed_at else None,
    )


@router.post("/run", response_model=TournamentOutcomeRead)
def run_tournament(
    req: TournamentRunRequest, db: Session = Depends(get_db)
) -> TournamentOutcomeRead:
    """اجرای تورنمنت روی اهداف و روش‌های داده‌شده."""
    if not req.targets:
        raise HTTPException(status_code=422, detail="targets must not be empty")
    outcome = TournamentEngine(db).run(
        targets=req.targets,
        methods=req.methods,
        horizon=req.horizon,
        scenario=req.scenario,
        name=req.name,
    )
    return TournamentOutcomeRead(**outcome.as_dict())


@router.get("", response_model=list[TournamentRead])
def list_tournaments(
    limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)
) -> list[TournamentRead]:
    stmt = (
        select(Tournament).order_by(Tournament.created_at.desc()).limit(limit)
    )
    return [_to_tournament(t) for t in db.execute(stmt).scalars().all()]


@router.get("/{tournament_id}", response_model=TournamentRead)
def get_tournament(
    tournament_id: uuid.UUID, db: Session = Depends(get_db)
) -> TournamentRead:
    tournament = db.get(Tournament, tournament_id)
    if tournament is None:
        raise HTTPException(status_code=404, detail="tournament not found")
    return _to_tournament(tournament)
