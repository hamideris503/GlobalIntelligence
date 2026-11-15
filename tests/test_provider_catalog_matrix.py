"""WP-07 — نگهبان ماتریس Provider/Catalog/Policy (آفلاین، بدون HTTP واقعی).

این تست‌ها همان واقعیت‌هایی را قفل می‌کنند که گزارش WP-07 به آن‌ها استناد می‌کند:

- هر جفت (provider, model) در allowlist باید adapter داشته باشد؛ وگرنه ادعای
  «مدل مجاز» بدون کد اجرایی است.
- هر جفت active باید شاهد منبع/تاریخ/محدودیت/حریم داشته باشد و منقضی نباشد.
- هر جفت disabled باید دلیل مشخص داشته باشد (نه سکوت).
- Kev/Laya رانتایم محلی‌اند، نه Provider ابری و نه عضو allowlist ابری.
- Free Policy در حالت غیر-mock هرگز mock را جای Real نمی‌گذارد.
- نگاشت خطا به HTTP صریح است (403/503/502/504) تا «BLOCKED» بی‌صدا نشود.

هیچ تستی به شبکه، کلید یا مقدار Secret نیاز ندارد.
"""
from __future__ import annotations

from backend.ai import free_policy
from backend.ai.free_policy import (
    FREE_ALLOWLIST,
    LOCAL_PROVIDERS,
    active_pairs,
    check_model,
    check_provider,
)
from backend.ai.providers.registry import available_providers
from backend.ai.schemas.types import AIErrorKind
from backend.api.errors import AI_ERROR_STATUS, SAFE_MESSAGES

CLOUD_POLICY_PROVIDERS = {e.provider for e in FREE_ALLOWLIST} - set(LOCAL_PROVIDERS)


def test_every_policy_entry_has_an_adapter() -> None:
    adapters = set(available_providers())
    missing = sorted(CLOUD_POLICY_PROVIDERS - adapters)
    assert missing == [], f"policy entry بدون adapter: {missing}"
    # Local runtimes هم باید adapter داشته باشند ولی عضو allowlist ابری نباشند.
    assert LOCAL_PROVIDERS <= adapters
    assert not (LOCAL_PROVIDERS & {e.provider for e in FREE_ALLOWLIST})


def test_active_entries_carry_evidence_and_are_not_expired() -> None:
    active = [e for e in FREE_ALLOWLIST if e.status == "active"]
    assert active, "هیچ جفت مجاز فعالی وجود ندارد"
    for entry in active:
        assert entry.source, f"{entry.provider}: منبع تأیید نامشخص"
        assert entry.verified_on is not None, f"{entry.provider}: تاریخ تأیید نامشخص"
        assert entry.limits, f"{entry.provider}: محدودیت رایگان نامشخص"
        assert entry.account, f"{entry.provider}: نوع حساب نامشخص"
        assert entry.privacy, f"{entry.provider}: وضعیت حریم نامشخص"
        assert not free_policy._expired(entry), (
            f"{entry.provider}/{entry.model}: تأیید منقضی شده ({entry.verified_on})"
        )
    pairs = active_pairs()
    assert pairs == [(e.provider, e.model) for e in active], (
        "active_pairs باید دقیقاً همان جفت‌های active و منقضی‌نشده باشد"
    )


def test_disabled_entries_state_a_reason() -> None:
    disabled = [e for e in FREE_ALLOWLIST if e.status != "active"]
    assert disabled, "allowlist بدون هیچ ورودی غیرفعال مشکوک است"
    for entry in disabled:
        assert entry.disabled_reason, f"{entry.provider}/{entry.model}: دلیل غیرفعال‌بودن خالی است"


def test_policy_denials_are_explicit_and_not_retryable() -> None:
    import pytest

    from backend.ai.schemas.types import AIError

    # mock در حالت Real ممنوع است (جای Real را نمی‌گیرد).
    with pytest.raises(AIError) as mock_exc:
        check_provider("mock", mock_mode=False)
    assert mock_exc.value.kind == AIErrorKind.provider_not_allowed
    assert mock_exc.value.retryable is False

    # provider خارج از allowlist.
    with pytest.raises(AIError) as unknown:
        check_provider("some_cloud", mock_mode=False)
    assert unknown.value.kind == AIErrorKind.provider_not_allowed

    # جفت غیرفعال: دلیل باید در پیام باشد و retry نداشته باشد.
    disabled = next(e for e in FREE_ALLOWLIST if e.status != "active" and e.provider not in LOCAL_PROVIDERS)
    with pytest.raises(AIError) as disabled_exc:
        check_model(disabled.provider, disabled.model, mock_mode=False)
    assert disabled_exc.value.kind == AIErrorKind.model_not_allowed
    assert disabled_exc.value.retryable is False
    assert disabled.disabled_reason[:25] in str(disabled_exc.value)

    # مدل ناشناخته حتی برای provider مجاز رد می‌شود (حدس مدل ممنوع).
    with pytest.raises(AIError) as guess:
        check_model("groq", "made-up-model", mock_mode=False)
    assert guess.value.kind == AIErrorKind.model_not_allowed


def test_blocked_states_map_to_explicit_http_statuses() -> None:
    assert AI_ERROR_STATUS[AIErrorKind.provider_not_allowed] == 403
    assert AI_ERROR_STATUS[AIErrorKind.model_not_allowed] == 403
    assert AI_ERROR_STATUS[AIErrorKind.free_unavailable] == 503
    assert AI_ERROR_STATUS[AIErrorKind.auth] == 502
    assert AI_ERROR_STATUS[AIErrorKind.timeout] == 504
    for kind in (
        AIErrorKind.provider_not_allowed,
        AIErrorKind.model_not_allowed,
        AIErrorKind.free_unavailable,
        AIErrorKind.auth,
        AIErrorKind.rate_limit,
        AIErrorKind.quota_exhausted,
        AIErrorKind.budget,
    ):
        assert SAFE_MESSAGES[kind], f"{kind}: پیام امن خالی است"


def test_local_runtimes_are_not_counted_as_cloud_providers() -> None:
    cloud = [p for p in available_providers() if p not in LOCAL_PROVIDERS and p != "mock"]
    assert "kev" not in cloud and "laya" not in cloud
    assert cloud == [
        "openai", "anthropic", "gemini", "openrouter", "groq", "cloudflare",
        "openai_compatible",
    ]
