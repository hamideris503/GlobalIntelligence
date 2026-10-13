"""AI priority fallback — فقط از AI Gateway موجود، فقط در عدم قطعیت.

پاسخ AI داده غیرقابل‌اعتماد است: اعتبارسنجی ساختاری، بدون اجرای هیچ دستوری.
"""
from __future__ import annotations

from typing import Any

PRIORITY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["priority", "confidence", "reason", "reason_codes"],
    "properties": {
        "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3", "P4"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string", "maxLength": 280},
        "reason_codes": {"type": "array", "items": {"type": "string", "maxLength": 32}, "maxItems": 8},
    },
    "additionalProperties": False,
}

TASK = "source_priority"
ROLE = "source_priority"  # نقش مستقل تا route task-specific واقعاً درگیر شود (نه fast_extraction)


def validate_ai_priority(payload: Any) -> dict | None:
    """برگرداندن payload تمیز یا None. هرگز حدس نمی‌زند."""
    if not isinstance(payload, dict):
        return None
    prio = payload.get("priority")
    conf = payload.get("confidence")
    reason = payload.get("reason")
    codes = payload.get("reason_codes")
    if prio not in ("P0", "P1", "P2", "P3", "P4"):
        return None
    try:
        conf_f = float(conf)
    except (TypeError, ValueError):
        return None
    if not (0.0 <= conf_f <= 1.0):
        return None
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 280:
        return None
    if not isinstance(codes, list) or len(codes) > 8:
        return None
    clean_codes = [str(c)[:32] for c in codes if isinstance(c, str) and c.strip()]
    return {"priority": prio, "confidence": conf_f, "reason": reason.strip(), "reason_codes": clean_codes}


async def ai_prioritize(*, title: str | None, text: str | None, metadata: dict | None = None) -> dict | None:
    """فراخوانی Gateway؛ خطا/نامعتبر -> None (fallback قواعد می‌ماند).

    نتیجه شامل `is_mock` است تا پاسخ mock هرگز به‌جای تصمیم واقعی اعمال نشود.
    """
    try:
        from backend.ai.gateway import get_gateway
        from backend.ai.schemas.types import AIRequest, Message
    except Exception:  # noqa: BLE001
        return None
    snippet = (text or "")[:1500]
    prompt = (
        "Assign ingestion priority P0..P4 to this news item. "
        "Reply ONLY with JSON matching the schema. "
        f"Title: {title or ''}\nText: {snippet}\n"
        f"Meta: {(metadata or {})}"
    )
    req = AIRequest(
        messages=[Message(role="user", content=prompt)],
        task=TASK, role=ROLE, temperature=0.0, max_tokens=300,
        json_schema=PRIORITY_SCHEMA, metadata={"untrusted_input": True},
    )
    try:
        resp = await get_gateway().generate(req)
        import json as _json

        payload = _json.loads(resp.text or "{}")
        clean = validate_ai_priority(payload)
        if clean is None:
            return None
        clean["is_mock"] = bool(resp.is_mock)
        return clean
    except Exception:  # noqa: BLE001
        return None
