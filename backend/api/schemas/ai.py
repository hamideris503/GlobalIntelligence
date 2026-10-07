"""Pydantic schemas for the AI API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AIMessage(BaseModel):
    role: str = "user"
    content: str


class AIGenerateRequest(BaseModel):
    messages: list[AIMessage] = Field(..., min_length=1)
    role: str | None = None
    task: str | None = None
    temperature: float = 0.2
    max_tokens: int | None = None
    model_metadata: dict[str, Any] | None = None


class AIUsageRead(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class AIGenerateResponse(BaseModel):
    text: str
    provider: str
    model: str
    usage: AIUsageRead
    cost_estimate: float | None = None
    latency_ms: float | None = None
    model_version: str | None = None
    prompt_version: str | None = None


class AIProviderHealth(BaseModel):
    provider: str
    healthy: bool
    detail: str = ""
