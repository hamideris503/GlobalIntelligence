"""AI API — مسیر مستقل برای آزمون Gateway (محافظت‌شده با API key)."""
from __future__ import annotations

from fastapi import APIRouter

from backend.ai.gateway import get_gateway
from backend.ai.schemas.types import AIRequest, Message
from backend.api.schemas.ai import (
    AIGenerateRequest,
    AIGenerateResponse,
    AIProviderHealth,
    AIUsageRead,
)

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/generate", response_model=AIGenerateResponse)
async def generate(payload: AIGenerateRequest) -> AIGenerateResponse:
    gateway = get_gateway()
    request = AIRequest(
        messages=[Message(role=m.role, content=m.content) for m in payload.messages],  # type: ignore[arg-type]
        role=payload.role,
        task=payload.task,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        # توجه: metadata از کاربر پذیرفته نمی‌شود (جلوگیری از انتخاب مدل/تایم‌اوت)
    )
    response = await gateway.generate(request)
    return AIGenerateResponse(
        text=response.text,
        provider=response.provider,
        model=response.model,
        usage=AIUsageRead(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
        ),
        cost_estimate=response.cost_estimate,
        latency_ms=response.latency_ms,
        model_version=response.model_version,
        prompt_version=response.prompt_version,
        is_mock=response.is_mock,
    )


@router.get("/providers", response_model=list[AIProviderHealth])
async def providers() -> list[AIProviderHealth]:
    gateway = get_gateway()
    return [
        AIProviderHealth(provider=h.provider, healthy=h.healthy, detail=h.detail)
        for h in await gateway.provider_health()
    ]
