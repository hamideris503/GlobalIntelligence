"""Knowledge Graph API (Phase 15).

- POST /api/graph/extract     → ساخت گراف از Eventهای پردازش‌نشده
- GET  /api/graph/entities    → لیست موجودیت‌ها (فیلتر نوع)
- GET  /api/graph/entities/{id} → یک موجودیت + روابطش
- GET  /api/graph/relationships → لیست روابط (فیلتر kind/entity)
- GET  /api/graph/neighbors/{id} → همسایه‌های یک موجودیت
"""
from __future__ import annotations

import uuid

from domains.graph.engine import KnowledgeGraphEngine
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.entity import Entity, EntityRelationship
from backend.database.session import get_db

router = APIRouter(prefix="/api/graph", tags=["graph"])


class GraphOutcomeRead(BaseModel):
    events_processed: int
    entities_created: int
    entities_updated: int
    relationships_created: int
    rejected: int
    failed: int
    errors: list[str]


class EntityRead(BaseModel):
    id: str
    type: str
    canonical_name: str
    display_name: str | None
    aliases: list[str]
    country: str | None


class RelationshipRead(BaseModel):
    id: str
    from_entity_id: str
    to_entity_id: str
    relation: str
    weight: float | None
    confidence: float | None


class NeighborRead(BaseModel):
    direction: str  # outgoing | incoming
    relation: str
    entity: EntityRead
    weight: float | None


def _parse_aliases(raw: str | None) -> list[str]:
    import json

    if not raw:
        return []
    try:
        out = json.loads(raw)
        return out if isinstance(out, list) else []
    except Exception:  # noqa: BLE001
        return []


def _to_entity(e: Entity) -> EntityRead:
    return EntityRead(
        id=str(e.id),
        type=e.type,
        canonical_name=e.canonical_name,
        display_name=e.display_name,
        aliases=_parse_aliases(e.aliases),
        country=e.country,
    )


def _to_rel(r: EntityRelationship) -> RelationshipRead:
    return RelationshipRead(
        id=str(r.id),
        from_entity_id=str(r.from_entity_id),
        to_entity_id=str(r.to_entity_id),
        relation=r.relation,
        weight=r.weight,
        confidence=r.confidence,
    )


@router.post("/extract", response_model=GraphOutcomeRead)
async def extract_graph(
    limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)
) -> GraphOutcomeRead:
    """ساخت موجودیت‌ها و روابط از رویدادهای پردازش‌نشده."""
    outcome = await KnowledgeGraphEngine(db).run(limit=limit)
    return GraphOutcomeRead(**outcome.as_dict())


@router.get("/entities", response_model=list[EntityRead])
def list_entities(
    entity_type: str | None = Query(default=None, alias="type"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[EntityRead]:
    stmt = select(Entity).order_by(Entity.canonical_name).limit(limit).offset(offset)
    if entity_type:
        stmt = stmt.where(Entity.type == entity_type)
    return [_to_entity(e) for e in db.execute(stmt).scalars().all()]


@router.get("/entities/{entity_id}", response_model=EntityRead)
def get_entity(entity_id: uuid.UUID, db: Session = Depends(get_db)) -> EntityRead:
    entity = db.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="entity not found")
    return _to_entity(entity)


@router.get("/relationships", response_model=list[RelationshipRead])
def list_relationships(
    relation: str | None = None,
    entity_id: str | None = None,
    limit: int = Query(default=200, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> list[RelationshipRead]:
    stmt = select(EntityRelationship).limit(limit)
    if relation:
        stmt = stmt.where(EntityRelationship.relation == relation)
    if entity_id:
        try:
            eid = uuid.UUID(entity_id)
        except ValueError:
            return []
        stmt = stmt.where(
            (EntityRelationship.from_entity_id == eid)
            | (EntityRelationship.to_entity_id == eid)
        )
    return [_to_rel(r) for r in db.execute(stmt).scalars().all()]


@router.get("/neighbors/{entity_id}", response_model=list[NeighborRead])
def neighbors(
    entity_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[NeighborRead]:
    entity = db.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="entity not found")
    out: list[NeighborRead] = []
    for r in entity.outgoing:
        out.append(
            NeighborRead(
                direction="outgoing",
                relation=r.relation,
                entity=_to_entity(r.to_entity),
                weight=r.weight,
            )
        )
    for r in entity.incoming:
        out.append(
            NeighborRead(
                direction="incoming",
                relation=r.relation,
                entity=_to_entity(r.from_entity),
                weight=r.weight,
            )
        )
    return out
