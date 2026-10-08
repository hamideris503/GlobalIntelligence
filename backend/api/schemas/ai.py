"""Pydantic schemas for the AI API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AIMessage(BaseModel):
    role: str = "user"
    content: str = Field(..., max_length=20000)


class AIGenerateRequest(BaseModel):
    messages: list[AIMessage] = Field(..., min_length=1, max_length=50)
    role: str | None = None
    task: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=8000)


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
    is_mock: bool = False


class AIProviderHealth(BaseModel):
    provider: str
    healthy: bool
    detail: str = ""
