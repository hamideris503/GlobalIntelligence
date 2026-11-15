"""AI API — مسیر مستقل برای آزمون Gateway (محافظت‌شده با API key)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

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
from backend.database.models.ai_settings import AIProviderRow
from backend.database.session import get_db

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
async def chat(payload: AIChatRequest, db: Session = Depends(get_db)) -> AIGenerateResponse:
    """گفت‌وگوی متنی با provider/model انتخابی کاربر (اعتبارسنجی سمت سرور).

    - provider تهی یعنی پیش‌فرض Gateway؛ در غیر این صورت باید ردیف DB فعال
      یا kind پیکربندی‌شده در .env باشد (در غیر این صورت 422).
    - model تهی یعنی پیش‌فرض همان provider.
    - metadata از کاربر پذیرفته نمی‌شود (جلوگیری از force/timeout دلخواه).
    - session از dependency استاندارد `get_db` می‌آید (در تست‌ها override می‌شود).
    """
    from backend.ai import credentials_store as store

    metadata: dict = {}
    # زمینهٔ داده‌ها: خلاصهٔ کوتاه از DB تا مدل بتواند به سؤال‌های مبتنی بر داده پاسخ دهد.
    context_parts: list[str] = []
    try:
        from sqlalchemy import func as _func

        from backend.database.models import (
            alert as _alert_m,
        )
        from backend.database.models import (
            article as _article_m,
        )
        from backend.database.models import (
            forecast as _forecast_m,
        )
        from backend.database.models import (
            risk_assessment as _risk_m,
        )
        from backend.database.models import (
            source as _source_m,
        )
        def _count(model) -> int:
            try:
                from sqlalchemy import select as _select
                return int(db.execute(_select(_func.count()).select_from(model)).scalar() or 0)
            except Exception:  # noqa: BLE001
                return 0
        counts = {
            "sources": _count(_source_m.Source),
            "articles": _count(_article_m.Article),
            "forecasts": _count(_forecast_m.Forecast),
            "risk_assessments": _count(_risk_m.RiskAssessment),
            "alerts": _count(_alert_m.Alert),
        }
        context_parts.append("COUNTS: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    except Exception:  # noqa: BLE001
        pass
    if context_parts:
        # prepend as system message if not already present
        msgs = [m for m in payload.messages]
        has_system = any(getattr(m, "role", None) == "system" for m in msgs)
        if not has_system:
            from backend.ai.schemas.types import Message as _Msg
            payload_messages_with_ctx = [_Msg(role="system", content="You are an assistant with access to the GlobalIntelligence app data.\n" + "\n".join(context_parts))] + list(payload.messages)
        else:
            payload_messages_with_ctx = list(payload.messages)
    else:
        payload_messages_with_ctx = list(payload.messages)
    if payload.provider:
        try:
            rows = (
                db.execute(select(AIProviderRow).where(AIProviderRow.enabled.is_(True)))
                .scalars()
                .all()
            )
            ok = any(r.name == payload.provider or r.kind == payload.provider for r in rows)
        except Exception:  # noqa: BLE001 — قطعی DB نباید providerهای .env را ببندد
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
        messages=[Message(role=m.role, content=m.content) for m in payload_messages_with_ctx],  # type: ignore[arg-type]
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
