"""Debate API schemas (Step 3)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class DebateRunRequest(BaseModel):
    target: str = Field(..., min_length=3, max_length=255)
    horizon_days: int = Field(default=30, ge=1, le=730)
    dry_run: bool = False
    live: bool = False
    max_rounds: int | None = Field(default=None, ge=1, le=5)


class DebateRunResponse(BaseModel):
    run_id: str | None = None
    status: str
    consensus: float | None = None
    disagreement: float | None = None
    confidence: float | None = None
    forecast_ids: list[str] = []
    total_tokens: int = 0
    total_cost: float | None = None
    errors: list[str] = []


class DebateMessageRead(BaseModel):
    id: str
    round_no: int
    agent: str
    provider: str | None
    model: str | None
    probability_up: float | None
    confidence: float | None
    quality_score: float | None
    total_tokens: int | None
    cost_estimate: float | None
    latency_ms: float | None
    error: str | None


class DebateRunRead(BaseModel):
    id: str
    target: str
    target_date: str | None
    horizon_days: int | None
    status: str
    context_hash: str | None
    reference_price: float | None
    consensus_probability: float | None
    disagreement: float | None
    total_tokens: int | None
    total_cost_estimate: float | None
    messages: list[DebateMessageRead] = []
