"""AI API — مسیر مستقل برای آزمون Gateway (محافظت‌شده با API key)."""
from __future__ import annotations

from fastapi import APIRouter

from backend.ai.gateway import get_gateway
from backend.ai.schemas.types import AIRequest, Message
from backend.api.schemas.ai import (
    AIChatRequest,
    AIGenerateRequest,
    AIGenerateResponse,
    AIProviderHealth,
    AIStatusRead,
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


@router.get("/status", response_model=AIStatusRead)
def ai_status() -> AIStatusRead:
    """وضعیت مؤثر اجرا (Mock/واقعی با override پنل)، پیش‌فرض و نقش‌ها."""
    from backend.ai import credentials_store as store
    from backend.ai.routing.router import DEFAULT_ROUTES

    return AIStatusRead(
        mock_mode=store.effective_mock_mode(),
        default_provider=store.effective_default_provider(),
        roles=sorted(DEFAULT_ROUTES),
    )


@router.post("/chat", response_model=AIGenerateResponse)
async def chat(payload: AIChatRequest) -> AIGenerateResponse:
    """گفت‌وگوی متنی با provider/model انتخابی کاربر (اعتبارسنجی سمت سرور).

    - provider تهی یعنی پیش‌فرض Gateway؛ در غیر این صورت باید ردیف DB فعال
      یا kind پیکربندی‌شده در .env باشد (در غیر این صورت 422).
    - model تهی یعنی پیش‌فرض همان provider.
    - metadata از کاربر پذیرفته نمی‌شود (جلوگیری از force/timeout دلخواه).
    """
    from fastapi import HTTPException

    from backend.ai import credentials_store as store

    metadata: dict = {}
    if payload.provider:
        ok = False
        try:
            from sqlalchemy import select as _select

            from backend.database.models.ai_settings import AIProviderRow
            from backend.database.session import get_session_factory

            session = get_session_factory()()
            try:
                rows = session.execute(
                    _select(AIProviderRow).where(AIProviderRow.enabled.is_(True))
                ).scalars().all()
                ok = any(r.name == payload.provider or r.kind == payload.provider
                         for r in rows)
            finally:
                session.close()
        except Exception:  # noqa: BLE001
            ok = False
        if not ok:
            try:
                ok = any(i["kind"] == payload.provider or i["name"] == payload.provider
                         for i in store.list_env_providers())
            except Exception:  # noqa: BLE001
                ok = False
        if not ok:
            raise HTTPException(status_code=422, detail="unknown or disabled provider")
        metadata["force_provider"] = payload.provider
    if payload.model:
        metadata["model"] = payload.model
    gateway = get_gateway()
    request = AIRequest(
        messages=[Message(role=m.role, content=m.content) for m in payload.messages],  # type: ignore[arg-type]
        role="chat",
        task="interactive_chat",
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        metadata=metadata,
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
