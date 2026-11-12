"""Profile registry — ثبت و بازیابی پروفایل‌های کشور (Stage 99).

پروفایل IR به‌عنوان پروفایل پایه (پیش‌فرض) ثبت شده است.
پروفایل دوم فقط با ثبت در registry (بدون تغییر کد موتورها) اضافه می‌شود.
"""

from __future__ import annotations

from domains.country_profile.profile import CountryProfile

# پروفایل پایهٔ ایران — معادل رفتار قبلی (Phase 33)
IR_PROFILE = CountryProfile(
    code="IR",
    country_codes=frozenset({"IR", "IRN"}),
    name_keywords=frozenset({"iran", "iranian"}),
    target_keywords=("irn", "iran"),
    source_domain_suffixes=(".ir",),
    macro_country_code="IRN",
    languages=("fa", "en"),
    assets=("WTI", "BRENT", "XAUUSD", "US10Y", "SPX"),
    transmission_channels=("energy", "rates", "geopolitical", "market"),
    weights={"energy": 0.9, "rates": 0.6, "geopolitical": 0.8, "market": 0.5},
    report_settings={"title": "Iran Brief"},
    version="v1",
)

_PROFILES: dict[str, CountryProfile] = {IR_PROFILE.code: IR_PROFILE}


def register_profile(profile: CountryProfile) -> None:
    """ثبت/به‌روزرسانی پروفایل. بدون تغییر کد موتورها."""
    _PROFILES[profile.code.upper()] = profile


def get_profile(code: str) -> CountryProfile | None:
    return _PROFILES.get(code.strip().upper())


def list_profiles() -> list[CountryProfile]:
    return list(_PROFILES.values())


def default_profile() -> CountryProfile:
    return IR_PROFILE


__all__ = ["IR_PROFILE", "register_profile", "get_profile", "list_profiles", "default_profile"]