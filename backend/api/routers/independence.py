"""Source Independence API (Phase 14).

- POST /api/independence/run       → اجرای تحلیل استقلال روی Claimها
- GET  /api/independence/dependencies → لیست یال‌های وابستگی
- POST /api/independence/dependencies → افزودن یال وابستگی دستی
- DELETE /api/independence/dependencies/{id}
- GET  /api/independence/groups    → گروه‌های وابستگی منابع
"""
from __future__ import annotations

import uuid

from domains.news.independence import (
    SourceDependencyService,
    SourceIndependenceEngine,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database.session import get_db

router = APIRouter(prefix="/api/independence", tags=["independence"])


class IndependenceOutcomeRead(BaseModel):
    sources: int
    dependency_edges: int
    groups: int
    claims_processed: int
    claims_with_sources: int
    corroborated: int
    failed: int
    errors: list[str]


class DependencyCreate(BaseModel):
    source_id: uuid.UUID
    depends_on_id: uuid.UUID
    kind: str = "manual"
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    detected_by: str = "manual"


class DependencyRead(BaseModel):
    id: str
    source_id: str
    depends_on_id: str
    kind: str
    weight: float
    detected_by: str


class SourceGroupRead(BaseModel):
    representative: str
    members: list[str]


def _to_dep_read(dep) -> DependencyRead:
    return DependencyRead(
        id=str(dep.id),
        source_id=str(dep.source_id),
        depends_on_id=str(dep.depends_on_id),
        kind=dep.kind,
        weight=dep.weight,
        detected_by=dep.detected_by,
    )


@router.post("/run", response_model=IndependenceOutcomeRead)
def run_independence(
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> IndependenceOutcomeRead:
    """تشخیص وابستگی منابع و محاسبه‌ی تأیید مستقل برای Claimها."""
    outcome = SourceIndependenceEngine(db).run(limit=limit)
    return IndependenceOutcomeRead(**outcome.as_dict())


@router.get("/dependencies", response_model=list[DependencyRead])
def list_dependencies(
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
) -> list[DependencyRead]:
    return [_to_dep_read(d) for d in SourceDependencyService(db).list(limit=limit)]


@router.post("/dependencies", response_model=DependencyRead, status_code=201)
def add_dependency(
    payload: DependencyCreate, db: Session = Depends(get_db)
) -> DependencyRead:
    if payload.source_id == payload.depends_on_id:
        raise HTTPException(status_code=400, detail="source cannot depend on itself")
    dep = SourceDependencyService(db).add(
        payload.source_id,
        payload.depends_on_id,
        kind=payload.kind,
        weight=payload.weight,
        detected_by=payload.detected_by,
    )
    return _to_dep_read(dep)


@router.delete("/dependencies/{dependency_id}", status_code=204, response_class=Response)
def delete_dependency(dependency_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    if not SourceDependencyService(db).delete(dependency_id):
        raise HTTPException(status_code=404, detail="dependency not found")
    return Response(status_code=204)


@router.get("/groups", response_model=list[SourceGroupRead])
def list_groups(db: Session = Depends(get_db)) -> list[SourceGroupRead]:
    mapping, _n, _e = SourceIndependenceEngine(db).build_groups()
    groups: dict[str, list[str]] = {}
    for sid, rep in mapping.items():
        groups.setdefault(rep, []).append(sid)
    return [
        SourceGroupRead(representative=rep, members=sorted(members))
        for rep, members in sorted(groups.items())
    ]
