"""Research API (Phase 52).

- POST /api/research/graphrag → بازیابی زیرگراف + سنتز اختیاری
"""
from __future__ import annotations

from domains.research.graphrag import DEFAULT_HOPS, DEFAULT_LIMIT, GraphRAGService
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database.session import get_db

router = APIRouter(prefix="/api/research", tags=["research"])


class GraphRAGRequest(BaseModel):
    entity_names: list[str]
    hops: int = DEFAULT_HOPS
    limit: int = DEFAULT_LIMIT
    synthesize: bool = False


class GraphRAGRead(BaseModel):
    seed_entities: list[dict]
    nodes: list[dict]
    edges: list[dict]
    hops: int
    truncated: bool
    synthesis: dict


@router.post("/graphrag", response_model=GraphRAGRead)
async def graphrag(
    req: GraphRAGRequest, db: Session = Depends(get_db)
) -> GraphRAGRead:
    """بازیابی زیرگراف k-hop برای موجودیت‌ها (+ سنتز اختیاری)."""
    if not req.entity_names:
        raise HTTPException(status_code=422, detail="entity_names must not be empty")
    if not 0 <= req.hops <= 5:
        raise HTTPException(status_code=422, detail="hops must be 0..5")
    if not 1 <= req.limit <= 500:
        raise HTTPException(status_code=422, detail="limit must be 1..500")
    service = GraphRAGService(db)
    ctx = service.retrieve(
        entity_names=req.entity_names, hops=req.hops, limit=req.limit
    )
    if req.synthesize:
        ctx.synthesis = await service.synthesize(ctx)
    return GraphRAGRead(**ctx.as_dict())


@router.get("/methods")
def research_methods() -> dict:
    """وضعیت تکنیک‌های تحقیقاتی (پیاده‌شده / به‌تعویق‌افتاده با دلیل)."""
    return {
        "implemented": ["graphrag_lite"],
        "deferred": {
            "bayesian_networks": "needs pgmpy dependency + larger conditional datasets",
            "causal_discovery": "needs long stationary time series (Phase 16/17 history too short)",
        },
    }
