"""Matching — قواعد تطبیق (Phase 33).

پس از Stage 99، منطق تطبیق به ``domains.country_profile`` منتقل شده است.
این ماژول برای سازگاری با کد قبلی، پروفایل پایهٔ IR را استفاده می‌کند.
رفتار ایران قبل/بعد یکسان است (تست مقایسه‌ای).
"""

from __future__ import annotations

from domains.country_profile.matching import (
    parse_str_list,
)
from domains.country_profile.profile import CountryProfile
from domains.country_profile.registry import IR_PROFILE

# ثابت‌های قبلی (برای سازگاری)
COUNTRY_CODES = frozenset({"IR", "IRN"})
NAME_KEYWORDS = frozenset({"iran", "iranian"})

# پروفایل فعال (پیش‌فرض IR)
_active_profile: CountryProfile = IR_PROFILE


def set_active_profile(profile: CountryProfile) -> None:
    global _active_profile
    _active_profile = profile


def get_active_profile() -> CountryProfile:
    return _active_profile


def is_iran_country(code: str | None) -> bool:
    return _active_profile.matches_country(code)


def is_iran_name(name: str | None) -> bool:
    return _active_profile.matches_name(name)


def is_iran_target(target: str | None) -> bool:
    return _active_profile.matches_target(target)


def is_iran_source(name: str | None, domain: str | None) -> bool:
    return _active_profile.matches_source(name, domain)


__all__ = [
    "COUNTRY_CODES",
    "NAME_KEYWORDS",
    "is_iran_country",
    "is_iran_name",
    "is_iran_source",
    "is_iran_target",
    "parse_str_list",
    "set_active_profile",
    "get_active_profile",
]