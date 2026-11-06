"""Catalog of AI providers the Settings panel knows how to configure.

Discovery aid only: never creates a provider or spends money on its own.
"""
from __future__ import annotations

from dataclasses import dataclass

from backend.ai.free_policy import FREE_ALLOWLIST, FreeModel


@dataclass(frozen=True)
class CatalogEntry:
    kind: str
    display_name: str
    description: str
    required_fields: tuple[str, ...]
    suggested_models: tuple[str, ...]
    free_policy_status: str
    free_policy_note: str
    docs_url: str
    account_hint: str = ""


_DISPLAY = {
    "gemini": "Google Gemini",
    "groq": "Groq",
    "cloudflare": "Cloudflare Workers AI",
    "openrouter": "OpenRouter",
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "openai_compatible": "OpenAI-compatible (custom base URL)",
    "mock": "Mock (dev only)",
}


def _note_for(model: FreeModel) -> str:
    if model.status == "active":
        return "active - " + model.limits if model.limits else "active"
    return model.disabled_reason or "disabled"


def _build() -> tuple[CatalogEntry, ...]:
    by_kind: dict[str, list[FreeModel]] = {}
    for m in FREE_ALLOWLIST:
        by_kind.setdefault(m.provider, []).append(m)

    entries: list[CatalogEntry] = []
    for kind, models in by_kind.items():
        primary = models[0]
        required: tuple[str, ...] = ("api_key",)
        if kind == "cloudflare":
            required = ("api_key", "account_id")
        elif kind == "openai_compatible":
            required = ("base_url",)
        entries.append(
            CatalogEntry(
                kind=kind,
                display_name=_DISPLAY.get(kind, kind),
                description="Provider kind '" + kind + "' supported by the AI Gateway.",
                required_fields=required,
                suggested_models=tuple(m.model for m in models),
                free_policy_status=primary.status,
                free_policy_note=_note_for(primary),
                docs_url=primary.source,
                account_hint=primary.account,
            )
        )
    if "mock" not in by_kind:
        entries.append(
            CatalogEntry(
                kind="mock",
                display_name="Mock (dev only)",
                description="Deterministic mock provider for development and tests.",
                required_fields=(),
                suggested_models=(),
                free_policy_status="n/a",
                free_policy_note="dev only; stripped from the chain in production",
                docs_url="",
                account_hint="no credentials",
            )
        )
    entries.sort(key=lambda e: e.kind)
    return tuple(entries)


CATALOG: tuple[CatalogEntry, ...] = _build()


def as_dicts() -> list[dict]:
    return [
        {
            "kind": e.kind,
            "display_name": e.display_name,
            "description": e.description,
            "required_fields": list(e.required_fields),
            "suggested_models": list(e.suggested_models),
            "free_policy_status": e.free_policy_status,
            "free_policy_note": e.free_policy_note,
            "docs_url": e.docs_url,
            "account_hint": e.account_hint,
        }
        for e in CATALOG
    ]
