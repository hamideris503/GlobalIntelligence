"""اینترفیس یکسان Provider (بند 12-13).

نام Providerها در منطق اصلی hard-code نمی‌شود؛ همه از این اینترفیس پیروی می‌کنند.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

from backend.ai.schemas.types import AIRequest, AIResponse, Message, ProviderHealth


@runtime_checkable
class AIProvider(Protocol):
    """قرارداد هر Provider. پیاده‌سازی‌ها باید نام یکتا داشته باشند."""

    name: str

    async def generate(self, request: AIRequest) -> AIResponse:
        ...

    async def health(self) -> ProviderHealth:
        ...


class BaseProvider(ABC):
    """پیاده‌سازی پایه با کمک‌تابع‌های مشترک."""

    name: str = "base"

    @abstractmethod
    async def generate(self, request: AIRequest) -> AIResponse:
        raise NotImplementedError

    async def structured_generate(
        self, request: AIRequest, schema: dict[str, Any]
    ) -> AIResponse:
        """تولید خروجی ساختاریافته؛ Providerهای واقعی می‌توانند override کنند."""
        req = AIRequest(
            messages=request.messages,
            task=request.task,
            role=request.role,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            json_schema=schema,
            metadata=request.metadata,
        )
        return await self.generate(req)

    async def classify(self, text: str, labels: list[str]) -> AIResponse:
        prompt = (
            "Classify the following text into exactly one of these labels: "
            f"{', '.join(labels)}.\n\nText:\n{text}"
        )
        return await self.generate(AIRequest(messages=[Message.user(prompt)]))

    async def extract(self, text: str, schema: dict[str, Any]) -> AIResponse:
        prompt = (
            "Extract structured data from the text according to the schema."
            f"\n\nText:\n{text}"
        )
        return await self.structured_generate(
            AIRequest(messages=[Message.user(prompt)]), schema
        )

    async def health(self) -> ProviderHealth:  # pragma: no cover - پیش‌فرض
        return ProviderHealth(provider=self.name, healthy=True, detail="ok")
