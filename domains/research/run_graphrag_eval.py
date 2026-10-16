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

آزمون زنده عمداً پیاده نشده است: تعداد واقعی تلاش‌های provider در این لایه
قابل محدودسازی و ردیابی قابل‌اعتماد نیست (retry داخلی Gateway + fallback
زنجیره). بنابراین `--allow-live-provider` صرفاً درخواست را رد می‌کند و
هیچ درخواست شبکه‌ای ارسال نمی‌شود.
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
    GraphContext,
    GraphRAGService,
)

DEFAULT_EDGE_COUNTS = (10, 30, DEFAULT_LIMIT)  # سقف واقعی = DEFAULT_LIMIT
# همان برشِ as_text()[:4000] در synthesize (فقط برای پرچم truncated).
PROMPT_CONTEXT_CHARS = 4000

LIVE_REFUSAL = (
    "live provider probe is not implemented: the real number of provider "
    "attempts cannot be bounded/traced at this layer (Gateway internal retry "
    "+ chain fallback), so no network call is made. Offline mode only."
)


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

    def __init__(self, response: dict) -> None:
        self.response = response
        self.requests: list[AIRequest] = []

    async def structured_generate(self, request: AIRequest, schema: dict) -> AIResponse:
        self.requests.append(request)
        return AIResponse(
            text=json.dumps(self.response, ensure_ascii=False),
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


def evaluate_sample(n_edges: int, response: dict | None = None) -> dict:
    """یک نمونه‌ی آفلاین: مسیر واقعی synthesize + Gateway ضبط‌کننده."""
    ctx = synthetic_context(n_edges)
    fake = response if response is not None else synthetic_response(n_edges)
    recorder = _RecordingGateway(fake)
    service = GraphRAGService(None)
    # مسیر LLM را بدون تغییر تنظیمات محیطی فعال می‌کنیم (کپی محلی).
    service._settings = service._settings.model_copy(update={"mock_mode": False})
    service.gateway = recorder

    out = asyncio.run(service.synthesize(ctx))
    request = recorder.requests[0]
    user_content = request.messages[-1].content or ""
    context_chars = len(ctx.as_text())
    synthetic_chars = len(json.dumps(out, ensure_ascii=False))

    return {
        "edges": n_edges,
        "nodes": len(ctx.nodes),
        "context_chars": context_chars,
        "context_truncated": context_chars > PROMPT_CONTEXT_CHARS,
        "input_chars": len(user_content),
        "input_tokens_estimate": budget.estimate_input_tokens(request),
        "output_cap_effective": budget.resolve_output_cap(request),
        "output_schema_valid": is_valid_synth_output(fake),
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GraphRAG synthesis offline eval")
    parser.add_argument("--edges", type=int, nargs="+",
                        default=list(DEFAULT_EDGE_COUNTS))
    parser.add_argument("--allow-live-provider", action="store_true",
                        help="درخواست آزمون زنده (فعلاً رد می‌شود)")
    args = parser.parse_args(argv)

    if args.allow_live_provider:
        print(json.dumps({"mode": "live", "error": LIVE_REFUSAL},
                         ensure_ascii=False, indent=2))
        return 2

    print(json.dumps(run_eval(tuple(args.edges)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
