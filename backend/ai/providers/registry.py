"""Registry Providerها — کشف و ساخت Providerها بر اساس نام.

نام Providerها فقط اینجا نگاشت می‌شوند؛ منطق اصلی آن‌ها را hard-code نمی‌کند.
"""
from __future__ import annotations

from backend.ai.providers.anthropic import AnthropicProvider
from backend.ai.providers.base import AIProvider
from backend.ai.providers.gemini import GeminiProvider
from backend.ai.providers.mock import MockProvider
from backend.ai.providers.openai import OpenAIProvider
from backend.ai.providers.openrouter import OpenRouterProvider

# نگاشت نام → کلاس. افزودن Provider جدید فقط با یک خط اینجا انجام می‌شود.
_PROVIDER_CLASSES: dict[str, type] = {
    "mock": MockProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "openrouter": OpenRouterProvider,
}


def available_providers() -> list[str]:
    return list(_PROVIDER_CLASSES.keys())


def build_provider(name: str) -> AIProvider:
    cls = _PROVIDER_CLASSES.get(name)
    if cls is None:
        raise ValueError(f"unknown provider: {name}")
    return cls()
