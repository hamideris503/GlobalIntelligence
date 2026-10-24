"""Free-only AI policy — Step 1D enforcement tests (all offline, no network).

- Unknown/paid models are rejected before any HTTP.
- DB/panel/adaptive paths go through the same central gate.
- Daily-quota exhaustion is distinct from transient rate limits.
- Quota exhaustion keeps data pending; nothing is deleted.
"""
from __future__ import annotations

import asyncio
from datetime import date

import httpx
import pytest

from backend.ai import free_policy
from backend.ai.gateway.gateway import AIGateway
from backend.ai.providers.base import BaseProvider
from backend.ai.providers.openai import OpenAIProvider
from backend.ai.schemas.types import (
    AIError,
    AIErrorKind,
    AIRequest,
    AIResponse,
    Message,
    ProviderHealth,
)

ALLOWED = ("groq", "openai/gpt-oss-20b")


def _req(**kw) -> AIRequest:
    return AIRequest(messages=[Message.user("hi")], **kw)


class _OkStub(BaseProvider):
    name = "groq"
    default_model = "openai/gpt-oss-20b"
    calls = 0

    async def generate(self, request: AIRequest) -> AIResponse:
        type(self).calls += 1
        return AIResponse(text="ok", provider=self.name, model="m")

    async def health(self) -> ProviderHealth:
        return ProviderHealth(provider=self.name, healthy=True)


def _gateway(name="groq", model="openai/gpt-oss-20b") -> AIGateway:
    gw = AIGateway()
    gw._settings.mock_mode = False
    gw._settings.ai_default_provider = name
    stub = _OkStub()
    stub.default_model = model
    type(stub).calls = 0
    gw._providers[name] = stub
    return gw


# 1) مدل ناشناس/پولی در chat پیش از هر HTTP رد می‌شود
def test_chat_paid_model_rejected_before_http() -> None:
    gw = _gateway()
    stub = gw._providers["groq"]
    req = _req(role="chat", task="interactive_chat",
               metadata={"model": "gpt-5-pro"}, max_tokens=100)
    with pytest.raises(AIError) as exc:
        asyncio.run(gw.generate(req))
    assert exc.value.kind == AIErrorKind.model_not_allowed
    assert stub.calls == 0


def test_chat_unknown_provider_rejected_before_http() -> None:
    gw = AIGateway()
    gw._settings.mock_mode = False
    gw._settings.ai_default_provider = "no-such-provider"
    with pytest.raises(AIError) as exc:
        asyncio.run(gw.generate(_req()))
    assert exc.value.kind == AIErrorKind.provider_not_allowed


# 2) metadata["model"] دلخواه نمی‌تواند فهرست را دور بزند
def test_metadata_model_bypass_blocked() -> None:
    gw = _gateway()
    stub = gw._providers["groq"]
    with pytest.raises(AIError) as exc:
        asyncio.run(gw.generate(_req(metadata={"model": "claude-opus-4-6"})))
    assert exc.value.kind == AIErrorKind.model_not_allowed
    assert stub.calls == 0


def test_exact_allowlisted_pair_passes() -> None:
    gw = _gateway()
    resp = asyncio.run(gw.generate(_req()))
    assert resp.text == "ok"
    assert gw._providers["groq"].calls == 1


# 3) force_provider/DB/adaptive نمی‌توانند مسیر غیرمجاز بسازند
def test_force_provider_off_list_blocked_without_http() -> None:
    gw = _gateway()
    stub = gw._providers["groq"]
    req = _req(metadata={"force_provider": "openai"})
    with pytest.raises(AIError) as exc:
        asyncio.run(gw.generate(req))
    assert exc.value.kind in (AIErrorKind.provider_not_allowed,
                              AIErrorKind.model_not_allowed)
    assert stub.calls == 0


def test_adaptive_chain_off_list_blocked_without_http() -> None:
    from backend.ai.routing.router import Route

    gw = _gateway()
    stub = gw._providers["groq"]
    gw.set_routes({"probe": Route("probe", ["openai", "groq"])})
    req = AIRequest(messages=[Message.user("hi")], task="probe", role="probe")
    with pytest.raises(AIError) as exc:
        asyncio.run(gw.generate(req))
    assert exc.value.kind == AIErrorKind.model_not_allowed
    assert stub.calls == 0


def test_disabled_entry_model_blocked() -> None:
    assert free_policy._find("openai", "gpt-4o-mini").status == "disabled"
    with pytest.raises(AIError) as exc:
        free_policy.check_model("openai", "gpt-4o-mini", mock_mode=False)
    assert exc.value.kind == AIErrorKind.model_not_allowed


# 4) fallback هرگز به غیرمجاز نمی‌رود
def test_fallback_never_reaches_disallowed() -> None:
    class _Flaky(BaseProvider):
        name = "groq"
        default_model = "openai/gpt-oss-20b"

        async def generate(self, request: AIRequest) -> AIResponse:
            raise AIError("busy", kind=AIErrorKind.rate_limit, retryable=True)

        async def health(self) -> ProviderHealth:
            return ProviderHealth(provider=self.name, healthy=True)

    from backend.ai.routing.router import Route

    gw = AIGateway()
    gw._settings.mock_mode = False
    gw._max_retries = 0
    gw._providers["groq"] = _Flaky()
    gw.set_routes({"probe": Route("probe", ["groq", "openai"])})
    req = AIRequest(messages=[Message.user("hi")], task="probe", role="probe")
    with pytest.raises(AIError) as exc:
        asyncio.run(gw.generate(req))
    # اولین نامزد مجاز شکست خورد؛ دومی غیرمجاز → توقف، نه fallback
    assert exc.value.kind == AIErrorKind.model_not_allowed


def test_all_quota_exhausted_maps_to_free_unavailable() -> None:
    class _Quota(BaseProvider):
        name = "groq"
        default_model = "openai/gpt-oss-20b"

        async def generate(self, request: AIRequest) -> AIResponse:
            raise AIError("daily quota exhausted", kind=AIErrorKind.quota_exhausted,
                          retryable=False)

        async def health(self) -> ProviderHealth:
            return ProviderHealth(provider=self.name, healthy=True)

    gw = AIGateway()
    gw._settings.mock_mode = False
    gw._settings.ai_default_provider = "groq"
    gw._providers["groq"] = _Quota()
    with pytest.raises(AIError) as exc:
        asyncio.run(gw.generate(_req()))
    assert exc.value.kind == AIErrorKind.free_unavailable


# 5) تنظیمات provider مجاز هم باید مدل دقیق را رعایت کند
def test_allowed_provider_with_off_list_default_model_blocked() -> None:
    gw = _gateway(name="groq", model="some-paid-model")
    stub = gw._providers["groq"]
    with pytest.raises(AIError) as exc:
        asyncio.run(gw.generate(_req()))
    assert exc.value.kind == AIErrorKind.model_not_allowed
    assert stub.calls == 0


# 6) اتمام سهمیه: متمایز، بدون retry بی‌فایده، بدون حذف داده
def _transport_429_daily():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429, json={"error": {"code": 429, "message": "Quota exceeded "
                                 "for metric, requests per day"}})

    import backend.ai.providers.http_base as hb

    orig = hb.httpx.AsyncClient
    transport = httpx.MockTransport(handler)

    def patched(*args, **kwargs):
        kwargs["transport"] = transport
        return orig(*args, **kwargs)

    hb.httpx.AsyncClient = patched
    return orig


def test_daily_quota_distinct_no_retry() -> None:
    import backend.ai.providers.http_base as hb

    orig = _transport_429_daily()
    try:
        p = OpenAIProvider()
        p.api_key = "test-key"
        with pytest.raises(AIError) as exc:
            asyncio.run(p.generate(_req()))
    finally:
        hb.httpx.AsyncClient = orig
    assert exc.value.kind == AIErrorKind.quota_exhausted
    assert exc.value.retryable is False


def test_retry_after_header_propagated() -> None:
    import backend.ai.providers.http_base as hb

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"retry-after": "7"},
                              json={"error": "slow down"})

    orig = hb.httpx.AsyncClient
    transport = httpx.MockTransport(handler)

    def patched(*args, **kwargs):
        kwargs["transport"] = transport
        return orig(*args, **kwargs)

    hb.httpx.AsyncClient = patched
    try:
        p = OpenAIProvider()
        p.api_key = "test-key"
        with pytest.raises(AIError) as exc:
            asyncio.run(p.generate(_req()))
    finally:
        hb.httpx.AsyncClient = orig
    assert exc.value.kind == AIErrorKind.rate_limit
    assert exc.value.retry_after == 7.0


def test_quota_keeps_classify_pending_without_attempt() -> None:
    from backend.database.models.article import Article
    from domains.news.classifier import ArticleClassifier
    from tests.conftest import TestingSession

    session = TestingSession()
    try:
        import asyncio as _asyncio

        async def _raise_quota(art):
            from backend.ai.schemas.types import AIError as _E
            from backend.ai.schemas.types import AIErrorKind as _K
            raise _E("daily quota exhausted", kind=_K.quota_exhausted)

        clf = ArticleClassifier(session)
        clf.classify_article = _raise_quota  # type: ignore[method-assign]
        from backend.database.models.document import Document
        from backend.database.models.source import Source

        article = Article(title="t", summary="s",
                          classification_status="pending",
                          classification_attempts=0)
        src = Source(name="Q", domain="q.local", type="rss", active=True)
        session.add(src)
        session.flush()
        doc = Document(source_id=src.id, title="t", raw_text="x")
        session.add(doc)
        session.flush()
        article.document_id = doc.id
        session.add(article)
        session.commit()
        result = _asyncio.run(clf.classify_pending(limit=5))
        session.refresh(article)
        assert article.classification_status == "pending"
        assert (article.classification_attempts or 0) == 0
        assert result.failed == 0
    finally:
        session.close()


# 7) mock فقط در mock mode؛ خروجی mock واقعی معرفی نمی‌شود
def test_mock_only_in_mock_mode() -> None:
    with pytest.raises(AIError) as exc:
        free_policy.check_provider("mock", mock_mode=False)
    assert exc.value.kind == AIErrorKind.provider_not_allowed
    free_policy.check_provider("mock", mock_mode=True)  # مجاز، بدون خطا

    gw = AIGateway()  # mock_mode پیش‌فرض True در تست
    resp = asyncio.run(gw.generate(_req(role="fast_extraction")))
    assert resp.provider == "mock" and resp.is_mock is True


# 8) قرارداد tasks با Gateway حفظ شده (نمونه: graphrag همچنان از Gateway می‌گذرد)
def test_tasks_still_use_gateway_contract() -> None:
    from domains.research.graphrag import GraphContext, GraphRAGService

    service = GraphRAGService(None)
    assert service.gateway is not None
    ctx = GraphContext(edges=[{"from": "A", "to": "B", "relation": "r",
                                "weight": 0.5, "confidence": 0.5}])
    assert len(ctx.as_text()) > 0


# 9) فقط providerهای محلی تأییدشده (Kev/Laya) اضافه شده‌اند
def test_no_local_providers_registered() -> None:
    from backend.ai.providers.registry import available_providers

    allowed_names = {"mock", "openai", "anthropic", "gemini", "openrouter",
                     "groq", "cloudflare", "openai_compatible", "kev", "laya"}
    names = set(available_providers())
    assert names <= allowed_names
    # Stage 45: Kev/Laya are the only approved local providers.
    assert not any("ollama" in n or "vllm" in n or "local" in n
                   for n in names - {"kev", "laya"})


# 10) انقضای تأیید → مسدود (نبود اطلاعات = مجاز نیست)
def test_expired_verification_blocks(monkeypatch) -> None:
    import backend.ai.free_policy as policy

    monkeypatch.setattr(policy, "_utc_today", lambda: date(2030, 1, 1))
    assert policy.active_pairs() == []
    with pytest.raises(AIError) as exc:
        policy.check_model("groq", "openai/gpt-oss-20b", mock_mode=False)
    assert exc.value.kind == AIErrorKind.model_not_allowed
    assert "expired" in str(exc.value)


def test_active_pairs_lists_only_groq() -> None:
    assert free_policy.active_pairs() == [ALLOWED]
