"""DB-backed credentials for the AI Gateway (Step 8).

اولویت: DB (ai_providers) > .env. بدون factory (تست/اسکریپت) فقط .env.
کلیدها فقط در حافظه‌ی همین فرایند رمزگشایی می‌شوند و هرگز لاگ/برگردانده نمی‌شوند.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.ai.credentials import CredentialError, decrypt_secret
from backend.core.logging import get_logger

logger = get_logger(__name__)

_factory = None
_version = 0

SECRET_LIKE = ("KEY", "SECRET", "PASSWORD", "TOKEN")


def set_session_factory(factory) -> None:  # noqa: ANN001
    global _factory
    _factory = factory


def bump_version() -> int:
    """ابطال کش Gateway پس از هر تغییر تنظیمات (بدون ری‌استارت)."""
    global _version
    _version += 1
    return _version


def get_version() -> int:
    return _version


def _session() -> Session | None:
    if _factory is None:
        return None
    try:
        return _factory()
    except Exception:  # noqa: BLE001
        return None


def is_secret_key(key: str) -> bool:
    upper = (key or "").upper()
    return any(token in upper for token in SECRET_LIKE)


def resolve_provider_credential(name: str) -> dict[str, Any] | None:
    """اعتبارنامه‌ی DB برای یک Provider (تطبیق kind و بعد name). None یعنی fallback به .env."""
    from backend.database.models.ai_settings import AIProviderRow

    db = _session()
    if db is None:
        return None
    try:
        rows = db.execute(
            select(AIProviderRow).where(AIProviderRow.enabled.is_(True))
        ).scalars().all()
        match = next((r for r in rows if r.kind == name), None)
        if match is None:
            match = next((r for r in rows if r.name == name), None)
        if match is None or not match.api_key_encrypted:
            return None
        try:
            api_key = decrypt_secret(match.api_key_encrypted)
        except CredentialError:
            logger.warning("credential decrypt failed for provider row (name hidden)")
            return None
        extra: dict = {}
        if match.extra_encrypted:
            try:
                import json as _json

                extra = _json.loads(decrypt_secret(match.extra_encrypted)) or {}
            except Exception:  # noqa: BLE001
                extra = {}
        models = sorted(
            [m for m in (match.models or []) if m.enabled],
            key=lambda m: m.created_at or datetime.min.replace(tzinfo=UTC),
        )
        return {
            "row_id": str(match.id),
            "name": match.name,
            "kind": match.kind,
            "base_url": match.base_url,
            "api_key": api_key,
            "extra": extra,
            "default_model": models[0].model_name if models else None,
        }
    finally:
        db.close()


def get_price_map() -> dict[tuple[str, str], tuple[float | None, float | None]]:
    """(provider_name, model) -> (price_in, price_out) برای ردیف‌های فعال."""
    from backend.database.models.ai_settings import AIModelRow, AIProviderRow

    db = _session()
    if db is None:
        return {}
    try:
        rows = db.execute(
            select(AIModelRow, AIProviderRow.name)
            .join(AIProviderRow, AIModelRow.provider_id == AIProviderRow.id)
            .where(AIModelRow.enabled.is_(True), AIProviderRow.enabled.is_(True))
        ).all()
        return {(prov_name, m.model_name): (m.price_in_per_mtok, m.price_out_per_mtok)
                for m, prov_name in rows}
    finally:
        db.close()


def find_price(provider_hint: str, model: str | None) -> tuple[float | None, float | None] | None:
    """قیمت (in, out) برای hint (نام یا kind) و مدل.

    - مدل None: فقط اگر دقیقاً یک مدل فعال برای این provider باشد همان (قاعده‌ی مستند).
    - mock همیشه رایگان است (0,0) — بدون ردیف قیمت.
    """
    if (provider_hint or "") == "mock":
        return (0.0, 0.0)
    from backend.database.models.ai_settings import AIModelRow, AIProviderRow

    db = _session()
    if db is None:
        return None
    try:
        rows = db.execute(
            select(AIModelRow, AIProviderRow)
            .join(AIProviderRow, AIModelRow.provider_id == AIProviderRow.id)
            .where(AIModelRow.enabled.is_(True), AIProviderRow.enabled.is_(True))
        ).all()
        mine = [(m, p) for m, p in rows
                if p.name == provider_hint or p.kind == provider_hint]
        if model:
            for m, _p in mine:
                if m.model_name == model:
                    return (m.price_in_per_mtok, m.price_out_per_mtok)
            return None
        if len(mine) == 1:
            m = mine[0][0]
            return (m.price_in_per_mtok, m.price_out_per_mtok)
        return None
    finally:
        db.close()


def compute_cost(usage_pt: int | None, usage_ct: int | None,
                 price: tuple[float | None, float | None] | None) -> float | None:
    """هزینه از توکن × قیمت ثبت‌شده. None یعنی قیمت/توکن نامشخص."""
    if price is None:
        return None
    pin, pout = price
    if pin is None and pout is None:
        return None
    return round((usage_pt or 0) / 1e6 * (pin or 0.0)
                 + (usage_ct or 0) / 1e6 * (pout or 0.0), 6)


def get_agent_mapping() -> dict[str, tuple[str, str | None]]:
    """agent -> (provider_name, model_name|None) برای نگاشت‌های فعال."""
    from backend.database.models.ai_settings import (
        AgentAssignment,
        AIModelRow,
        AIProviderRow,
    )

    db = _session()
    if db is None:
        return {}
    try:
        out: dict[str, tuple[str, str | None]] = {}
        for a in db.execute(
            select(AgentAssignment).where(AgentAssignment.enabled.is_(True))
        ).scalars().all():
            prov_name: str | None = None
            model_name: str | None = None
            if a.provider_id is not None:
                prow = db.get(AIProviderRow, a.provider_id)
                if prow is not None and prow.enabled:
                    prov_name = prow.name
            if a.model_id is not None:
                mrow = db.get(AIModelRow, a.model_id)
                if mrow is not None and mrow.enabled:
                    model_name = mrow.model_name
            if prov_name:
                out[a.agent] = (prov_name, model_name)
        return out
    finally:
        db.close()


def get_app_setting(db: Session, key: str, default: str | None = None) -> str | None:
    from backend.database.models.ai_settings import AppSetting

    row = db.get(AppSetting, key)
    return row.value if row is not None else default

def set_app_setting(db: Session, key: str, value: str | None) -> None:
    """ذخیره‌ی تنظیم غیرمحرمانه؛ کلید محرمانه رد می‌شود."""
    from backend.database.models.ai_settings import AppSetting

    if is_secret_key(key):
        raise CredentialError("secret-like keys cannot live in app_settings")
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value, updated_at=datetime.now(UTC)))
    else:
        row.value = value
        row.updated_at = datetime.now(UTC)


def _override(key: str) -> str | None:
    """خواندن override از app_settings (بدون factory → None یعنی .env)."""
    from backend.database.models.ai_settings import AppSetting

    db = _session()
    if db is None:
        return None
    try:
        row = db.get(AppSetting, key)
        return row.value if row is not None else None
    finally:
        db.close()


def effective_mock_mode() -> bool:
    """حالت Mock مؤثر: override دیتابیسی (از پنل) وگرنه .env. بدون ری‌استارت."""
    from backend.core.config import get_settings

    raw = _override("mock_mode")
    if raw is not None:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return bool(get_settings().mock_mode)


def effective_default_provider() -> str:
    """ارائه‌دهنده‌ی پیش‌فرض مؤثر: override دیتابیسی وگرنه .env."""
    from backend.core.config import get_settings

    raw = _override("ai_default_provider")
    if raw is not None and raw.strip():
        return raw.strip()
    return get_settings().ai_default_provider


ENV_PROVIDER_FIELDS: dict[str, tuple[str, str | None, str | None]] = {
    # kind -> (key_attr, base_attr, model_attr) روی Settings
    "gemini": ("gemini_api_key", "gemini_base_url", "gemini_model"),
    "openrouter": ("openrouter_api_key", "openrouter_base_url", "openrouter_model"),
    "openai": ("openai_api_key", "openai_base_url", "openai_model"),
    "anthropic": ("anthropic_api_key", "anthropic_base_url", "anthropic_model"),
    "groq": ("groq_api_key", "groq_base_url", "groq_model"),
    "cloudflare": ("cloudflare_api_token", None, None),
}

CLOUDFLARE_ACCOUNT_ATTR = "cloudflare_account_id"


def list_env_providers() -> list[dict[str, Any]]:
    """ارائه‌دهندگان پیکربندی‌شده در .env (فقط نام/وضعیت؛ بدون هیچ مقداری)."""
    from backend.core.config import get_settings

    settings = get_settings()
    out = []
    for kind, (key_attr, base_attr, _model_attr) in ENV_PROVIDER_FIELDS.items():
        key = getattr(settings, key_attr, None)
        if not key:
            continue
        if kind == "cloudflare" and not getattr(settings, CLOUDFLARE_ACCOUNT_ATTR, None):
            continue
        base = getattr(settings, base_attr, None) if base_attr else None
        out.append({"kind": kind, "name": kind, "base_url": base, "key_set": True})
    return out


def daily_spend_usd() -> float:
    """مصرف امروز از debate_messages (اعداد واقعی ثبت‌شده)."""
    from backend.database.models.debate import DebateMessage

    db = _session()
    if db is None:
        return 0.0
    try:
        total = db.execute(
            select(func.coalesce(func.sum(DebateMessage.cost_estimate), 0.0)).where(
                func.date(DebateMessage.created_at) == func.current_date()
            )
        ).scalars().one()
        return float(total or 0.0)
    finally:
        db.close()
