"""Registry Providerها — کشف و ساخت Providerها بر اساس نام.

نام Providerها فقط اینجا نگاشت می‌شوند؛ منطق اصلی آن‌ها را hard-code نمی‌کند.
Step 8: ساخت با اعتبارنامه‌ی DB (اولویت) و fallback به .env.
"""
from __future__ import annotations

from typing import Any

from backend.ai.providers.anthropic import AnthropicProvider
from backend.ai.providers.base import AIProvider
from backend.ai.providers.cloudflare import CloudflareProvider
from backend.ai.providers.gemini import GeminiProvider
from backend.ai.providers.groq import GroqProvider
from backend.ai.providers.local_decision import KevProvider, LayaProvider
from backend.ai.providers.mock import MockProvider
from backend.ai.providers.openai import OpenAIProvider
from backend.ai.providers.openai_compatible import OpenAICompatibleProvider
from backend.ai.providers.openrouter import OpenRouterProvider
from backend.core.logging import get_logger

logger = get_logger(__name__)

# نگاشت نام → کلاس. افزودن Provider جدید فقط با یک خط اینجا انجام می‌شود.
_PROVIDER_CLASSES: dict[str, type] = {
    "mock": MockProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "openrouter": OpenRouterProvider,
    "groq": GroqProvider,
    "cloudflare": CloudflareProvider,
    "openai_compatible": OpenAICompatibleProvider,
    # Local decision models (zero-cost, System One HTTP API).
    "kev": KevProvider,
    "laya": LayaProvider,
}


def available_providers() -> list[str]:
    return list(_PROVIDER_CLASSES.keys())


def build_provider(name: str, **kwargs: Any) -> AIProvider:
    cls = _PROVIDER_CLASSES.get(name)
    if cls is None:
        raise ValueError(f"unknown provider: {name}")
    try:
        return cls(**kwargs)  # type: ignore[call-arg]
    except TypeError:
        # Providerهای قدیمی kwargs نمی‌گیرند (.env fallback)
        return cls()


def build_provider_with_store(name: str) -> AIProvider:
    """ساخت با اعتبار DB؛ اگر نبود/نشد، رفتار قبلی (.env). بدون نشت secret در لاگ."""
    from backend.ai import credentials_store as store

    try:
        cred = store.resolve_provider_credential(name)
    except Exception:  # noqa: BLE001
        cred = None
    if cred is None:
        return build_provider(name)
    kind = cred["kind"]
    cls = _PROVIDER_CLASSES.get(kind)
    if cls is None:
        return build_provider(name)
    extra = cred.get("extra") or {}
    kwargs: dict[str, Any] = {"api_key": cred["api_key"]}
    if cred.get("base_url") and kind != "cloudflare":
        kwargs["base_url"] = cred["base_url"]
    if cred.get("default_model"):
        kwargs["default_model"] = cred["default_model"]
    if kind == "cloudflare":
        kwargs["account_id"] = extra.get("account_id")
    if kind == "mock":
        return build_provider("mock")
    try:
        return build_provider(kind, **kwargs)
    except Exception:  # noqa: BLE001
        logger.warning("DB-backed build failed; .env fallback (provider hidden)")
        return build_provider(name)
