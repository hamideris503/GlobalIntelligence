"""GraphRAG synthesis — offline evaluation harness (Step 1D.20).

هدف: اندازه‌گیری قطعی ورودی/خروجی مسیر واقعی `GraphRAGService.synthesize`
بدون هیچ تماس واقعی provider، تا بعداً بتوان یک سقف خروجی قابل‌دفاع برای
task گراف‌رگ انتخاب کرد. این ابزار هیچ سقف عملیاتی جدیدی ثبت نمی‌کند.

حالت پیش‌فرض کاملاً آفلاین است: مسیر واقعی `synthesize` اجرا می‌شود اما
Gateway با یک نمونه‌ی ضبط‌کننده‌ی بدون‌شبکه جایگزین می‌شود، پس ورودیِ واقعی
که به Gateway می‌رفت اندازه‌گیری می‌شود و خروجی ساختگی برچسب `synthetic`
می‌خورد. usage ساختگی هرگز به‌عنوان usage واقعی provider گزارش نمی‌شود.

اجرا:
    python -m domains.research.run_graphrag_eval
    python -m domains.research.run_graphrag_eval --edges 10 30 50

آزمون زنده فقط با opt-in سه‌گانه (‎--allow-live-provider + provider/model
صریح + ‎--acknowledge-cost) مجاز است: حداکثر ۳ ارسال واقعی در کل اجرا،
تک-provider بدون retry/fallback، سقف ۲۰۰۰ توکن اثبات‌شده در payload، و
ثبت harness-side بدون متن/secret. بودجه‌ی روزانه خاموش می‌ماند.
"""
from __future__ import annotations

import argparse
import asyncio
import json

from backend.ai import budget
from backend.ai.schemas.types import AIRequest, AIResponse, AIUsage
from domains.research.graphrag import (
    DEFAULT_LIMIT,
    SYNTH_SCHEMA,
    TRUNCATION_FINISH_REASONS,
    GraphContext,
    GraphRAGService,
)

DEFAULT_EDGE_COUNTS = (10, 30, DEFAULT_LIMIT)  # سقف واقعی = DEFAULT_LIMIT
# همان برشِ as_text()[:4000] در synthesize (فقط برای پرچم truncated).
PROMPT_CONTEXT_CHARS = 4000

# --- آزمون زنده‌ی محدود GraphRAG (Step 1D.27؛ پیش‌فرض: غیرفعال) ---
# سقف محافظ هر درخواست (نه سقف عملیاتی نهایی) و سقف کل ارسال‌های واقعی.
LIVE_MAX_TOKENS = 2000
LIVE_MAX_SENDS = 3
LIVE_EDGE_COUNTS = (10, 30, 50)

def _openai_cap_ok(payload: dict) -> bool:
    return payload.get("max_tokens") == LIVE_MAX_TOKENS


def _gemini_cap_ok(payload: dict) -> bool:
    gen = payload.get("generationConfig") or {}
    return gen.get("maxOutputTokens") == LIVE_MAX_TOKENS


# نگاشت provider -> بررسی اعمال سقف در payload واقعی همان provider.
# provider بدون بررسی اثبات‌شده (مثل cloudflare که max_tokens را نادیده
# می‌گیرد) و mock/ناشناخته → آزمون زنده مردود است.
LIVE_CAP_CHECKS = {
    "openai": _openai_cap_ok,
    "openai_compatible": _openai_cap_ok,
    "openrouter": _openai_cap_ok,
    "groq": _openai_cap_ok,
    "anthropic": _openai_cap_ok,
    "gemini": _gemini_cap_ok,
}

LIVE_REFUSAL = (
    "live provider probe refused: it requires --allow-live-provider together "
    "with --live-provider, --live-model and --acknowledge-cost; no network "
    "call is made without all of them. Offline mode only."
)


class LiveProbeRefused(Exception):
    """امتناع پیش از ارسال: شرط آزمون زنده برقرار نیست (بدون شبکه)."""


class LiveSendBudgetExceeded(Exception):
    """سقف ارسال واقعی تمام شد؛ این ارسال پیش از رفتن به شبکه رد شد."""


class HttpSendLimiter:
    """شمارنده‌ی سخت ارسال‌های HTTP واقعی (لایه‌ی client.post).

    پیش از هر ارسال واقعی افزایش می‌یابد؛ ارسالِ بیش از سقف، پیش از
    رفتن به شبکه رد می‌شود. تک‌نخی فرض شده (harness ترتیبی است).
    """

    def __init__(self, max_sends: int = LIVE_MAX_SENDS) -> None:
        self.max_sends = max_sends
        self.sends = 0

    def wrap_client_factory(self, real_factory):
        """factory ساخت AsyncClient را با نسخه‌ی شمارنده‌دار می‌پوشاند."""
        limiter = self

        def factory(*args, **kwargs):
            client = real_factory(*args, **kwargs)
            real_post = client.post

            async def counted_post(*post_args, **post_kwargs):
                if limiter.sends >= limiter.max_sends:
                    raise LiveSendBudgetExceeded(
                        f"live probe send budget exhausted "
                        f"({limiter.sends}/{limiter.max_sends})")
                limiter.sends += 1
                return await real_post(*post_args, **post_kwargs)

            client.post = counted_post
            return client

        return factory


def install_send_limiter(limiter: HttpSendLimiter):
    """نصب شمارنده روی لایه‌ی ارسال HTTP همه‌ی adapterها؛ orig را برمی‌گرداند."""
    import backend.ai.providers.http_base as http_base

    orig = http_base.httpx.AsyncClient
    http_base.httpx.AsyncClient = limiter.wrap_client_factory(orig)
    return orig


def restore_send_limiter(orig) -> None:
    """بازگردانی factory ارسال HTTP به حالت عادی."""
    import backend.ai.providers.http_base as http_base

    http_base.httpx.AsyncClient = orig


def synthetic_context(n_edges: int) -> GraphContext:
    """گراف مصنوعی و غیرحساس با n_edges یال (بدون DB، بدون داده‌ی واقعی)."""
    nodes = [
        {"id": f"n{i}", "name": f"Entity{i}", "type": "organization",
         "weighted_degree": 1.0}
        for i in range(n_edges + 1)
    ]
    edges = [
        {"from": f"Entity{i}", "to": f"Entity{i + 1}", "relation": "related_to",
         "weight": 0.5, "confidence": 0.5}
        for i in range(n_edges)
    ]
    return GraphContext(nodes=nodes, edges=edges, hops=2,
                        truncated=n_edges >= DEFAULT_LIMIT)


def validate_synth_output(data: dict) -> None:
    """اعتبارسنجی خروجی سنتز با همان SYNTH_SCHEMA (خروجی ناقص رد می‌شود)."""
    import jsonschema

    jsonschema.validate(instance=data, schema=SYNTH_SCHEMA)


def is_valid_synth_output(data: dict) -> bool:
    try:
        validate_synth_output(data)
        return True
    except Exception:  # noqa: BLE001
        return False


class _RecordingGateway:
    """Gateway بدون شبکه: درخواست واقعی را ضبط می‌کند و خروجی ساختگی می‌دهد."""

    def __init__(self, response: dict | None, text: str | None = None) -> None:
        self.response = response
        self.text = (text if text is not None
                     else json.dumps(response, ensure_ascii=False))
        self.requests: list[AIRequest] = []

    async def structured_generate(self, request: AIRequest, schema: dict) -> AIResponse:
        self.requests.append(request)
        return AIResponse(
            text=self.text,
            provider="synthetic",
            model="synthetic",
            usage=AIUsage(),  # هیچ usage واقعی provider ادعا نمی‌شود
            structured=self.response,
            is_mock=True,
        )


def synthetic_response(n_edges: int) -> dict:
    """خروجی ساختگی معتبر مطابق SYNTH_SCHEMA (خارج از provider واقعی)."""
    return {
        "summary": "synthetic summary (offline, no provider)",
        "key_relations": [f"Entity{i} related_to Entity{i + 1}"
                          for i in range(min(n_edges, 10))],
    }


def evaluate_sample(
    n_edges: int, response: dict | None = None, *, text: str | None = None,
) -> dict:
    """یک نمونه‌ی آفلاین: مسیر واقعی synthesize + Gateway ضبط‌کننده."""
    ctx = synthetic_context(n_edges)
    fake = response if response is not None else synthetic_response(n_edges)
    body = text if text is not None else json.dumps(fake, ensure_ascii=False)
    recorder = _RecordingGateway(fake if text is None else None, text=body)
    service = GraphRAGService(None)
    # مسیر LLM را بدون تغییر تنظیمات محیطی فعال می‌کنیم (کپی محلی).
    service._settings = service._settings.model_copy(update={"mock_mode": False})
    service.gateway = recorder

    out = asyncio.run(service.synthesize(ctx))
    request = recorder.requests[0]
    user_content = request.messages[-1].content or ""
    context_chars = len(ctx.as_text())
    synthetic_chars = len(json.dumps(out, ensure_ascii=False))
    try:
        fixture_data = json.loads(body)
    except Exception:  # noqa: BLE001
        fixture_data = None

    return {
        "edges": n_edges,
        "nodes": len(ctx.nodes),
        "context_chars": context_chars,
        "context_truncated": context_chars > PROMPT_CONTEXT_CHARS,
        "input_chars": len(user_content),
        "input_tokens_estimate": budget.estimate_input_tokens(request),
        "output_cap_effective": budget.resolve_output_cap(request),
        "output_schema_valid": is_valid_synth_output(fixture_data),
        "output_mode": out.get("mode"),
        "synthetic_output_chars": synthetic_chars,
        "synthetic_output_tokens_est": synthetic_chars // 4,
        "usage_source": "synthetic",
        "provider_usage": None,
        "synthetic": True,
    }


def run_eval(edge_counts: tuple[int, ...] = DEFAULT_EDGE_COUNTS) -> dict:
    """اجرای آفلاین روی همه‌ی تعدادهای یال؛ هیچ providerی صدا زده نمی‌شود."""
    return {
        "mode": "offline",
        "provider_calls": 0,
        "live_enabled": False,
        "note": "synthetic outputs only; not real provider usage",
        "samples": [evaluate_sample(n) for n in edge_counts],
    }


def build_live_plan(*, provider: str | None, model: str | None) -> dict:
    """اعتبارسنجی محض پارامترهای زنده (بدون ارسال، بدون شبکه).

    نام provider باید شناخته‌شده، غیر-mock و دارای بررسی سقف اثبات‌شده
    باشد؛ model باید صریح باشد؛ MOCK_MODE باید خاموش باشد (وگرنه زنجیره
    بی‌صدا به mock می‌رود).
    """
    from backend.core.mock_mode import effective_mock_mode

    if not provider or provider == "mock":
        raise LiveProbeRefused("live probe requires an explicit non-mock provider")
    if provider not in LIVE_CAP_CHECKS:
        raise LiveProbeRefused(
            f"live probe refuses provider {provider!r}: output-cap enforcement "
            f"not provable for this adapter")
    if not model or not model.strip():
        raise LiveProbeRefused("live probe requires an explicit model")
    if effective_mock_mode():
        raise LiveProbeRefused(
            "live probe refuses mock mode: the chain would silently use mock")
    return {
        "provider": provider,
        "model": model.strip(),
        "max_tokens": LIVE_MAX_TOKENS,
        "max_sends": LIVE_MAX_SENDS,
        "retries": 0,
        "chain": [provider],
        "samples": list(LIVE_EDGE_COUNTS),
    }


def check_live_provider(plan: dict):
    """ساخت provider با همان مسیر production + بررسی credential (بدون ارسال).

    credential هرگز چاپ نمی‌شود؛ نبود credential معتبر → امتناع پیش از ارسال.
    """
    from backend.ai.providers.registry import build_provider_with_store

    name = plan["provider"]
    try:
        provider = build_provider_with_store(name)
    except Exception as exc:  # noqa: BLE001
        raise LiveProbeRefused(
            f"live probe cannot build provider {name!r}") from exc
    provider.default_model = plan["model"]
    if not provider.configured():
        raise LiveProbeRefused(
            f"live probe has no valid credential for {name!r}; "
            f"stopping before any request")
    return provider


def build_live_gateway(plan: dict, provider):
    """نمونه‌ی تازه و مستقل Gateway برای آزمون: تک-provider، بدون retry.

    از routeهای اشتراکی runtime و singleton استفاده نمی‌شود؛ fallback
    با زنجیره‌ی تک‌عضوی و retries=۰ ناممکن است.
    """
    from backend.ai.gateway.gateway import AIGateway
    from backend.ai.routing.router import Route

    name = plan["provider"]
    gateway = AIGateway(routes={"deep_analysis": Route("deep_analysis", [name])})
    gateway._max_retries = 0
    gateway._providers[name] = provider
    route = gateway._route(_live_probe_request())
    if list(route.providers) != [name]:
        raise LiveProbeRefused("live probe chain is not single-provider")
    if gateway._max_retries != 0:
        raise LiveProbeRefused("live probe retries are not disabled")
    return gateway


def _live_probe_request():
    from backend.ai.schemas.types import AIRequest, Message

    return AIRequest(messages=[Message.user("probe")], role="deep_analysis",
                     task="graphrag_synthesize")


class _CappedLiveGateway:
    """تفویض به Gateway واقعی با سقف آزمایشی اثبات‌شده (harness-side).

    سقف دقیقاً ۲۰۰۰ روی همان AIRequest گذاشته و پیش از تفویض، اعمال آن
    در payload واقعی adapter بررسی می‌شود. هیچ سقف دائمی ثبت نمی‌کند.
    """

    def __init__(self, inner, provider, plan: dict) -> None:
        self._inner = inner
        self._provider = provider
        self._plan = plan
        self.cap_checks = 0
        self.last_response = None

    async def structured_generate(self, request, schema):
        if request.task != "graphrag_synthesize":
            raise LiveProbeRefused("live probe only serves graphrag_synthesize")
        request.max_tokens = LIVE_MAX_TOKENS
        if request.max_tokens != LIVE_MAX_TOKENS:
            raise LiveProbeRefused("live probe could not pin output cap")
        check = LIVE_CAP_CHECKS[self._plan["provider"]]
        self.cap_checks += 1
        if not check(self._provider._payload(request)):
            raise LiveProbeRefused(
                f"live probe cap not enforced in {self._plan['provider']} payload")
        self.last_response = await self._inner.structured_generate(request, schema)
        return self.last_response


def build_sample_evidence(
    *, run_id: str, provider: str, model: str, resolved_model: str | None,
    edges: int, context_chars: int, cap: int, sends_observed: int,
    finish_reason: str | None, usage, mode: str | None, stop_reason: str | None,
) -> dict:
    """رکورد غیرحساس یک نمونه (تابع محض؛ بدون شبکه، بدون متن/secret).

    usage=None هرگز صفر فرض نمی‌شود؛ finish ناموجود «گزارش‌نشده» است،
    نه «پایان طبیعی»؛ تخمین/کاراکتر با usage واقعی قاطی نمی‌شود.
    """
    return {
        "run_id": run_id,
        "provider": provider,
        "model": model,
        "resolved_model": resolved_model,
        "edges": edges,
        "context_chars": context_chars,
        "context_truncated": context_chars > PROMPT_CONTEXT_CHARS,
        "cap": cap,
        "sends_observed": sends_observed,
        "finish_reason": finish_reason,
        "finish_reported": finish_reason is not None,
        "truncated_output": finish_reason in TRUNCATION_FINISH_REASONS,
        "usage_in": getattr(usage, "prompt_tokens", None),
        "usage_out": getattr(usage, "completion_tokens", None),
        "usage_total": getattr(usage, "total_tokens", None),
        "mode": mode,
        "schema_ok": mode == "llm",
        "stop": stop_reason,
    }


def run_live_probe(
    *, provider: str | None, model: str | None, run_id: str | None = None,
) -> dict:
    """اجرای زنده‌ی محدود (حداکثر ۳ ارسال واقعی در کل اجرا).

    پیش‌شرط‌ها همه پیش از هر ارسال بررسی می‌شوند؛ بودجه‌ی روزانه خاموش
    می‌ماند (ثبت، harness-side است)؛ هیچ متنی/secretای ثبت نمی‌شود.
    در این مرحله اجرا نکن — فقط برای تأیید جداگانه‌ی آینده آماده است.
    """
    import uuid as _uuid

    plan = build_live_plan(provider=provider, model=model)
    real_provider = check_live_provider(plan)
    gateway = build_live_gateway(plan, real_provider)
    run = run_id or _uuid.uuid4().hex[:12]
    limiter = HttpSendLimiter(plan["max_sends"])
    orig = install_send_limiter(limiter)
    try:
        samples = []
        for n in plan["samples"]:
            before = limiter.sends
            ctx = synthetic_context(n)
            service = GraphRAGService(None)
            capped = _CappedLiveGateway(gateway, real_provider, plan)
            service.gateway = capped
            try:
                out = asyncio.run(service.synthesize(ctx))
                stop = out.get("reason")
                mode = out.get("mode")
            except LiveSendBudgetExceeded:
                mode, stop = "failed", "send_budget_exceeded"
            except Exception:  # noqa: BLE001 - terminal؛ تکرار همین نمونه ممنوع
                mode, stop = "failed", "terminal_error"
            resp = capped.last_response
            samples.append((n, ctx, mode, stop, resp, limiter.sends - before))
        evidence = [
            build_sample_evidence(
                run_id=run, provider=plan["provider"], model=plan["model"],
                resolved_model=getattr(resp, "model", None), edges=n,
                context_chars=len(ctx.as_text()), cap=plan["max_tokens"],
                sends_observed=delta,
                finish_reason=getattr(resp, "finish_reason", None),
                usage=getattr(resp, "usage", None),
                mode=mode, stop_reason=stop)
            for n, ctx, mode, stop, resp, delta in samples
        ]
        return {"mode": "live", "plan": {**plan, "run_id": run},
                "sends": limiter.sends, "samples": evidence}
    finally:
        restore_send_limiter(orig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GraphRAG synthesis offline eval")
    parser.add_argument("--edges", type=int, nargs="+",
                        default=list(DEFAULT_EDGE_COUNTS))
    parser.add_argument("--allow-live-provider", action="store_true",
                        help="opt-in صریح آزمون زنده (به‌تنهایی کافی نیست)")
    parser.add_argument("--live-provider", default=None,
                        help="provider صریح آزمون زنده (غیر mock)")
    parser.add_argument("--live-model", default=None,
                        help="model صریح آزمون زنده")
    parser.add_argument("--acknowledge-cost", action="store_true",
                        help="تأیید صریح هزینه‌ی احتمالی provider")
    args = parser.parse_args(argv)

    if args.allow_live_provider:
        missing = [name for name, ok in (
            ("--live-provider", bool(args.live_provider)),
            ("--live-model", bool(args.live_model)),
            ("--acknowledge-cost", bool(args.acknowledge_cost))) if not ok]
        if missing:
            print(json.dumps(
                {"mode": "live", "error": LIVE_REFUSAL,
                 "missing": missing}, ensure_ascii=False, indent=2))
            return 2
        try:
            report = run_live_probe(provider=args.live_provider,
                                    model=args.live_model)
        except LiveProbeRefused as exc:
            print(json.dumps({"mode": "live", "error": str(exc)},
                             ensure_ascii=False, indent=2))
            return 2
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(json.dumps(run_eval(tuple(args.edges)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
