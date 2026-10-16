"""GlobalIntelligence — Real AI connectivity check (Step 1).

یک درخواست کوچک واقعی به Provider تنظیم‌شده می‌زند و فقط این‌ها را چاپ می‌کند:
provider، model، توکن‌ها، latency، is_mock.

- کلید هرگز چاپ/لاگ نمی‌شود (هر رخداد مقدار کلید در متن‌ها سانسور می‌شود).
- `.env` کاربر دست نمی‌خورد؛ MOCK_MODE=false فقط در حافظه‌ی همین فرایند.
- اگر پاسخ mock بود یا خطا داد، با کد خروجی ۱ شکست می‌خورد.

اجرا:
    python scripts/check_ai.py [--provider gemini] [--max-tokens 64]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

# کنسول ویندوز ممکن است فارسی را خراب چاپ کند.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

# اجرای مستقیم (python scripts/check_ai.py): ریشه‌ی repo را به sys.path اضافه کن.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _redact(text: str, secrets: list[str]) -> str:
    for secret in secrets:
        if secret and len(secret) >= 8 and secret in text:
            text = text.replace(secret, "[REDACTED]")
    return text


async def _amain(provider: str, max_tokens: int, structured: bool) -> int:
    # mock خاموش فقط در همین فرایند (بدون دست‌زدن به .env)
    os.environ["MOCK_MODE"] = "false"
    os.environ["AI_DEFAULT_PROVIDER"] = provider

    from backend.ai.schemas.types import AIRequest, Message
    from backend.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    secrets = [
        settings.gemini_api_key or "",
        settings.openai_api_key or "",
        settings.anthropic_api_key or "",
        settings.openrouter_api_key or "",
        settings.api_key or "",
    ]

    from backend.ai.gateway import AIGateway

    gateway = AIGateway()
    schema: dict | None = None
    if structured:
        schema = {
            "type": "object",
            "properties": {
                "answer": {"type": "string"},
                "n": {"type": "integer"},
            },
            "required": ["answer", "n"],
        }
    request = AIRequest(
        messages=[Message.user(
            'Reply with JSON {"answer": "OK", "n": 1}.'
            if structured else "Reply with exactly: OK"
        )],
        task="connectivity_check",
        temperature=0.0,
        max_tokens=max_tokens,
        json_schema=schema,
    )
    started = time.perf_counter()
    try:
        if structured:
            response = await gateway.structured_generate(request, schema or {})
        else:
            response = await gateway.generate(request)
    except Exception as exc:  # noqa: BLE001
        kind = getattr(exc, "kind", type(exc).__name__)
        print(f"FAIL provider={provider} kind={kind}")
        print(f"detail={_redact(str(exc)[:300], secrets)}")
        return 1
    wall_ms = (time.perf_counter() - started) * 1000

    usage = response.usage
    print(f"provider={response.provider}")
    print(f"model={response.model}")
    print(f"tokens prompt={usage.prompt_tokens} completion={usage.completion_tokens} total={usage.total_tokens}")
    print(f"latency_ms={response.latency_ms or wall_ms:.1f}")
    print(f"is_mock={response.is_mock}")
    print(f"cost_estimate={response.cost_estimate}")
    print(f"text={_redact(response.text.strip()[:200], secrets)}")

    if response.is_mock:
        print("FAIL: response is mock, not real")
        return 1
    if response.provider != provider:
        print(f"FAIL: expected provider '{provider}', got '{response.provider}'")
        return 1
    if structured:
        import json as _json

        try:
            data = _json.loads(response.text.strip())
            assert isinstance(data, dict) and data.get("answer") == "OK" and data.get("n") == 1
            print("structured=PASS (valid JSON, schema keys ok)")
        except Exception as exc:  # noqa: BLE001
            print(f"structured=FAIL ({type(exc).__name__}: {_redact(str(exc)[:150], secrets)})")
            return 1
    print("PASS: real provider responded")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Real AI connectivity check")
    parser.add_argument("--provider", default="gemini")
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--structured", action="store_true",
                        help="also validate a small JSON-schema response")
    args = parser.parse_args(argv)
    return asyncio.run(_amain(args.provider, args.max_tokens, args.structured))


if __name__ == "__main__":
    raise SystemExit(main())
