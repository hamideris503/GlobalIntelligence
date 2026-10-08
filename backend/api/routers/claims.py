"""Claim & Evidence API (Phase 12/13)."""
from __future__ import annotations

import uuid

from domains.claims.evidence import EvidenceEngine
from domains.claims.extractor import ClaimExtractor
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.claim import Claim, Evidence
from backend.database.session import get_db

router = APIRouter(prefix="/api/claims", tags=["claims"])


class ClaimOutcomeRead(BaseModel):
    events_processed: int
    claims_created: int
    failed: int
    errors: list[str]


class EvidenceOutcomeRead(BaseModel):
    claims_processed: int
    evidence_created: int
    supports: int
    contradicts: int
    rejected: int = 0
    failed: int
    errors: list[str]


class EvidenceRead(BaseModel):
    id: str
    direction: str
    summary: str | None
    weight: float | None
    confidence: float | None


class ClaimRead(BaseModel):
    id: str
    event_id: str | None
    subject: str | None
    predicate: str | None
    object: str | None
    claim_type: str | None
    confidence: float | None
    verification_status: str
    evidence: list[EvidenceRead] = []


@router.post("/extract", response_model=ClaimOutcomeRead)
async def extract_claims(
    limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)
) -> ClaimOutcomeRead:
    """استخراج Claims از رویدادهای پردازش‌نشده."""
    outcome = await ClaimExtractor(db).run(limit=limit)
    return ClaimOutcomeRead(**outcome.as_dict())


@router.post("/evidence", response_model=EvidenceOutcomeRead)
async def collect_evidence(
    limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)
) -> EvidenceOutcomeRead:
    """جمع‌آوری شواهد موافق/مخالف برای Claims پردازش‌نشده."""
    outcome = await EvidenceEngine(db).run(limit=limit)
    return EvidenceOutcomeRead(**outcome.as_dict())


@router.get("", response_model=list[ClaimRead])
def list_claims(
    limit: int = Query(default=50, ge=1, le=500),
    event_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[ClaimRead]:
    stmt = select(Claim).order_by(Claim.created_at.desc()).limit(limit)
    if event_id:
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
            evidence=[
                EvidenceRead(
                    id=str(e.id),
                    direction=e.direction,
                    summary=e.summary,
                    weight=e.weight,
                    confidence=e.confidence,
                )
                for e in c.evidence
            ],
        )
        for c in rows
    ]


@router.get("/{claim_id}/evidence", response_model=list[EvidenceRead])
def list_claim_evidence(claim_id: str, db: Session = Depends(get_db)) -> list[EvidenceRead]:
    try:
        cid = uuid.UUID(claim_id)
    except ValueError:
        return []
    rows = (
        db.execute(select(Evidence).where(Evidence.claim_id == cid)).scalars().all()
    )
    return [
        EvidenceRead(
            id=str(e.id),
            direction=e.direction,
            summary=e.summary,
            weight=e.weight,
            confidence=e.confidence,
        )
        for e in rows
    ]
