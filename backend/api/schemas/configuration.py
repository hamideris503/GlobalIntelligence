"""Configuration control-plane schemas (F03.0) — بدون هیچ مقدار محرمانه."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class InstanceCreate(BaseModel):
    kind: str = Field(..., min_length=1, max_length=64)
    slug: str = Field(..., min_length=1, max_length=128)
    payload: dict
    note: str | None = None


class InstanceRead(BaseModel):
    id: str
    kind: str
    slug: str
    latest_revision: int
    active_revision: int | None = None
    active_status: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RevisionRead(BaseModel):
    id: str
    instance_id: str
    revision_number: int
    status: str
    payload: dict
    validation: dict | None = None
    test: dict | None = None
    descriptor_version: str
    actor: str
    note: str | None = None
    created_at: datetime | None = None
    activated_at: datetime | None = None


class InstanceDetail(InstanceRead):
    revisions: list[RevisionRead] = Field(default_factory=list)


class RevisionCreate(BaseModel):
    payload: dict
    expected_revision: int = Field(..., ge=0)
    note: str | None = None


class RevisionResult(BaseModel):
    revision: RevisionRead
    result: dict


class ActivateRequest(BaseModel):
    expected_revision: int = Field(..., ge=0)


class RollbackRequest(BaseModel):
    target_revision: int = Field(..., ge=1)
    expected_revision: int = Field(..., ge=0)
    note: str | None = None


class TestRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=20)
