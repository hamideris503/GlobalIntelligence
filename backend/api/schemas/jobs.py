"""Pydantic schemas for the jobs API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JobTriggerRequest(BaseModel):
    job_name: str = Field(..., min_length=1, max_length=128)
    source: str = Field(default="api", max_length=64)
    payload: dict[str, Any] | None = None


class JobRunRead(BaseModel):
    id: str
    job_name: str
    source: str | None
    status: str
    message: str | None
    started_at: datetime


class JobTriggerResponse(BaseModel):
    status: str
    job_run: JobRunRead
