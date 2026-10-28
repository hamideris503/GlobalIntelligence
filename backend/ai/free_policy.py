"""Free-only AI policy — central allowlist of (provider, model) pairs.

Every cloud request must pass `check_provider` + `check_model` before any
HTTP is sent (enforced in `AIGateway.generate`). Anything off-list, expired,
or disabled fails closed with a structured `AIError` — no fallback, no retry.
Local Kev/Laya endpoints are exempt: they run on our hardware and have no
cloud quota or API key to verify (see `LOCAL_PROVIDERS`).

Verification data below comes from the provider docs audited 2026-10-17.
Free tiers change: an entry past its review date is treated as blocked.
Absence of information never means allowed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, timedelta

from backend.ai.schemas.types import AIError, AIErrorKind

REVIEW_DAYS_DEFAULT = 90

# Local decision models run on our own hardware: no cloud quota, no key, no
# per-model free-tier evidence to verify. They are governed by the local
# screening settings, not by the cloud allowlist below.
LOCAL_PROVIDERS = frozenset({"kev", "laya"})


@dataclass(frozen=True)
class FreeModel:
    provider: str
    model: str
    status: str = "disabled"  # "active" | "disabled"
    source: str = ""
    verified_on: date | None = None
    review_days: int = REVIEW_DAYS_DEFAULT
    limits: str = ""
    account: str = ""
    disabled_reason: str = ""
    privacy: str = ""


FREE_ALLOWLIST: tuple[FreeModel, ...] = (
    FreeModel(
        provider="groq",
        model="openai/gpt-oss-20b",
        status="active",
        source="https://console.groq.com/docs/rate-limits",
        verified_on=date(2026, 10, 17),
        limits="30 RPM / 1000 RPD / 8K TPM, org-level; 429 carries retry-after",
        account="free, no card",
        privacy="no training on inputs/outputs any tier; no retention by "
                "default; self-serve ZDR",
    ),
    FreeModel(
        provider="cloudflare",
        model="@cf/meta/llama-3.1-8b-instruct",
        source="https://developers.cloudflare.com/workers-ai/platform/pricing/",
        verified_on=date(2026, 10, 17),
        limits="10000 Neurons/day free; overage fails on Free plan (no billing)",
        account="Workers Free (no card)",
        disabled_reason="model-level free eligibility on Workers Free unverified",
        privacy="unreviewed for this model",
    ),
    FreeModel(
        provider="gemini",
        model="gemini-3.5-flash",
        source="https://ai.google.dev/gemini-api/docs/pricing",
        verified_on=date(2026, 10, 17),
        limits="free tokens on Flash models; per-project RPM/TPM/RPD in AI Studio",
        account="free, no card",
        disabled_reason="EEA/CH/UK user-facing terms and unpaid data-use terms "
                        "pending clarification",
        privacy="unpaid content may be used to improve products + human review",
    ),
    FreeModel(
        provider="openai",
        model="gpt-4o-mini",
        source="https://help.openai.com/en/articles/8264644-setting-up-and-managing-prepaid-api-billing",
        verified_on=date(2026, 10, 17),
        disabled_reason="no free API tier (min $5 prepaid, auto-reload on)",
        privacy="API data not used for training; 30-day abuse logs",
    ),
    FreeModel(
        provider="anthropic",
        model="claude-3-5-haiku-latest",
        source="https://platform.claude.com/docs/en/about-claude/pricing",
        verified_on=date(2026, 10, 17),
        disabled_reason="no ongoing free tier (unstated test credit only)",
        privacy="commercial no-train posture (confirm current DPA)",
    ),
    FreeModel(
        provider="openrouter",
        model="openai/gpt-oss-20b:free",
        source="https://openrouter.ai/docs/api_reference/limits",
        verified_on=date(2026, 10, 17),
        limits="50 req/day (1000/day after $10 lifetime); rotating list",
        disabled_reason="blanket :free unsafe: rotating list, per-provider "
                        "training switches, negative balance blocks free",
        privacy="some free-model providers may train; switches must be off",
    ),
    FreeModel(
        provider="openai_compatible",
        model="*",
        source="",
        verified_on=date(2026, 10, 17),
        disabled_reason="no free-tier evidence for any exact pair; arbitrary "
                        "base_url must never imply free",
        privacy="unreviewed",
    ),
)


def _utc_today() -> date:
    from datetime import datetime

    return datetime.now(UTC).date()


def _expired(entry: FreeModel) -> bool:
    if entry.verified_on is None:
        return True
    return _utc_today() > entry.verified_on + timedelta(days=entry.review_days)


def _find(provider: str, model: str | None) -> FreeModel | None:
    return next(
        (e for e in FREE_ALLOWLIST if e.provider == provider and e.model == model),
        None)


def _provider_known(provider: str) -> bool:
    return any(e.provider == provider for e in FREE_ALLOWLIST)


def check_provider(name: str, *, mock_mode: bool) -> None:
    """Provider-level gate (before build). Raises provider_not_allowed."""
    if name == "mock":
        if mock_mode:
            return
        raise AIError("mock provider allowed only in mock mode",
                      kind=AIErrorKind.provider_not_allowed,
                      provider=name, retryable=False)
    if name in LOCAL_PROVIDERS:
        return
    if not _provider_known(name):
        raise AIError(f"provider not allowed: {name}",
                      kind=AIErrorKind.provider_not_allowed,
                      provider=name, retryable=False)


def check_model(name: str, model: str | None, *, mock_mode: bool) -> None:
    """Exact (provider, model) gate (before any HTTP). Raises model_not_allowed."""
    if name == "mock":
        return  # mock skips model pinning; provider gate already applied
    if name in LOCAL_PROVIDERS:
        return  # local model name is owned by the local server / settings
    entry = _find(name, model)
    if entry is None:
        raise AIError(f"model not allowed: {name}/{model}",
                      kind=AIErrorKind.model_not_allowed,
                      provider=name, retryable=False)
    if entry.status != "active":
        raise AIError(f"model not allowed: {name}/{model} "
                      f"({entry.disabled_reason or 'disabled'})",
                      kind=AIErrorKind.model_not_allowed,
                      provider=name, retryable=False)
    if _expired(entry):
        raise AIError(f"model not allowed: {name}/{model} "
                      f"(verification expired {entry.verified_on})",
                      kind=AIErrorKind.model_not_allowed,
                      provider=name, retryable=False)


def active_pairs() -> list[tuple[str, str]]:
    """Currently usable pairs (for docs/tests; expired/disabled excluded)."""
    out = []
    for e in FREE_ALLOWLIST:
        if e.status == "active" and not _expired(e):
            out.append((e.provider, e.model))
    return out


# --- DB-backed per-model verification (settings panel) ---
UNVERIFIED = "UNVERIFIED"
FREE_VERIFIED = "FREE_VERIFIED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"  # computed only, never stored
BLOCKED = "BLOCKED"


def effective_free_status(row) -> str:
    """Effective verification status of an AIModelRow-like object.

    Stored FREE_VERIFIED past its review date becomes REVIEW_REQUIRED.
    Missing/unknown stored value means UNVERIFIED. Never raises.
    """
    stored = getattr(row, "free_status", None) or UNVERIFIED
    if stored != FREE_VERIFIED:
        return stored if stored in (UNVERIFIED, BLOCKED) else UNVERIFIED
    verified_on = getattr(row, "free_verified_on", None)
    review_days = getattr(row, "free_review_days", None) or REVIEW_DAYS_DEFAULT
    if verified_on is None:
        return UNVERIFIED
    try:
        expired = _utc_today() > verified_on + timedelta(days=int(review_days))
    except Exception:  # noqa: BLE001
        return UNVERIFIED
    return REVIEW_REQUIRED if expired else FREE_VERIFIED


def is_free_verified(row) -> bool:
    """True only for fresh FREE_VERIFIED rows (usable as gateway default)."""
    return effective_free_status(row) == FREE_VERIFIED


def review_after(row) -> date | None:
    """Next review date, if verifiable."""
    verified_on = getattr(row, "free_verified_on", None)
    if verified_on is None:
        return None
    review_days = getattr(row, "free_review_days", None) or REVIEW_DAYS_DEFAULT
    try:
        return verified_on + timedelta(days=int(review_days))
    except Exception:  # noqa: BLE001
        return None
