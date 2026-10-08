"""Mock Provider — Provider پیش‌فرض برای توسعه‌ی بدون هزینه (Phase 6).

- هیچ API پولی یا اینترنت لازم نیست.
- خروجی deterministic و قابل پیش‌بینی است تا تست‌ها پایدار بمانند.
- از درخواست structured، یک JSON معتبر بر اساس schema می‌سازد.
"""
from __future__ import annotations

import json
import time
from typing import Any

from backend.ai.providers.base import BaseProvider
from backend.ai.schemas.types import (
    AIRequest,
    AIResponse,
    AIUsage,
    ProviderHealth,
)


def _mock_value_for_type(t: str, schema: dict[str, Any] | None = None) -> Any:
    if t in ("number", "integer"):
        value = 0
        if schema is not None and "minimum" in schema:
            value = max(value, schema["minimum"])
        if schema is not None and "maximum" in schema:
            value = min(value, schema["maximum"])
        return float(value) if t == "number" else int(value)
    return {
        "string": "mock",
        "boolean": False,
        "array": [],
        "object": {},
        "null": None,
    }.get(t, "mock")


def _mock_from_schema(schema: dict[str, Any]) -> Any:
    """نمونه‌ی معتبر و deterministic از JSON Schema (رعایت const/enum/default/anyOf/min/max)."""
    if not isinstance(schema, dict):
        return "mock"
    if "const" in schema:
        return schema["const"]
    if schema.get("enum"):
        return schema["enum"][0]
    if "default" in schema:
        return schema["default"]
    for key in ("anyOf", "oneOf"):
        if schema.get(key):
            options = [s for s in schema[key] if s.get("type") != "null"] or schema[key]
            return _mock_from_schema(options[0])

    stype = schema.get("type")
    if isinstance(stype, list):
        stype = next((t for t in stype if t != "null"), "null")

    if stype == "object" or "properties" in schema:
        props = schema.get("properties", {})
        required = schema.get("required", list(props.keys()))
        return {k: _mock_from_schema(v) for k, v in props.items() if k in required}
    if stype == "array":
        n = max(1, int(schema.get("minItems", 1)))
        return [_mock_from_schema(schema.get("items", {})) for _ in range(n)]
    return _mock_value_for_type(str(stype), schema)


class MockProvider(BaseProvider):
    name = "mock"

    async def generate(self, request: AIRequest) -> AIResponse:
        started = time.perf_counter()
        last_user = next(
            (m.content for m in reversed(request.messages) if m.role == "user"), ""
        )

        structured: dict[str, Any] | None = None
        if request.json_schema is not None:
            value = _mock_from_schema(request.json_schema)
            structured = value if isinstance(value, dict) else {"result": value}
            text = json.dumps(structured, ensure_ascii=False)
        else:
            text = f"[mock:{request.task or 'generate'}] {last_user[:200]}"

        latency = (time.perf_counter() - started) * 1000
        return AIResponse(
            text=text,
            provider=self.name,
            model=request.metadata.get("mock_model", "mock-1"),
            usage=AIUsage(prompt_tokens=len(last_user) // 4, completion_tokens=len(text) // 4,
                          total_tokens=(len(last_user) + len(text)) // 4),
            cost_estimate=0.0,
            latency_ms=latency,
            structured=structured,
            raw={"mock": True, "task": request.task, "role": request.role},
            model_version="mock-1",
            prompt_version=request.metadata.get("prompt_version", "v0"),
            is_mock=True,
        )

    async def health(self) -> ProviderHealth:
        return ProviderHealth(provider=self.name, healthy=True, detail="mock always ok")
