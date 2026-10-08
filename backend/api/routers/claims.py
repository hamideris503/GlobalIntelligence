"""Claim Extraction API (Phase 12)."""
from __future__ import annotations

from domains.claims.extractor import ClaimExtractor
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.claim import Claim
from backend.database.session import get_db

router = APIRouter(prefix="/api/claims", tags=["claims"])


class ClaimOutcomeRead(BaseModel):
    events_processed: int
    claims_created: int
    failed: int
    errors: list[str]


class ClaimRead(BaseModel):
    id: str
    event_id: str | None
    subject: str | None
    predicate: str | None
    object: str | None
    claim_type: str | None
    confidence: float | None
    verification_status: str


@router.post("/extract", response_model=ClaimOutcomeRead)
async def extract_claims(
    limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)
) -> ClaimOutcomeRead:
    """استخراج Claims از رویدادهای پردازش‌نشده."""
    outcome = await ClaimExtractor(db).run(limit=limit)
    return ClaimOutcomeRead(**outcome.as_dict())


@router.get("", response_model=list[ClaimRead])
def list_claims(
    limit: int = Query(default=50, ge=1, le=500),
    event_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[ClaimRead]:
    stmt = select(Claim).order_by(Claim.created_at.desc()).limit(limit)
    if event_id:
        import uuid

        try:
            stmt = stmt.where(Claim.event_id == uuid.UUID(event_id))
        except ValueError:
            pass
    rows = db.execute(stmt).scalars().all()
    return [
        ClaimRead(
            id=str(c.id),
            event_id=str(c.event_id) if c.event_id else None,
            subject=c.subject,
            predicate=c.predicate,
            object=c.object,
            claim_type=c.claim_type,
            confidence=c.confidence,
            verification_status=c.verification_status,
        )
        for c in rows
    ]
