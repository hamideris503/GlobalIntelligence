"""Profile-driven matching (Stage 99).

توابع تطبیق بر اساس CountryProfile. اگر profile داده نشود، پروفایل پایهٔ IR استفاده می‌شود
(رفتار قبلی حفظ می‌شود).
"""

from __future__ import annotations

import json

from domains.country_profile.profile import CountryProfile
from domains.country_profile.registry import IR_PROFILE


def _norm(text: str) -> str:
    return " ".join(text.strip().split()).casefold()


def is_country(profile: CountryProfile, code: str | None) -> bool:
    return profile.matches_country(code)


def is_name(profile: CountryProfile, name: str | None) -> bool:
    return profile.matches_name(name)


def is_target(profile: CountryProfile, target: str | None) -> bool:
    return profile.matches_target(target)


def is_source(profile: CountryProfile, name: str | None, domain: str | None) -> bool:
    return profile.matches_source(name, domain)


def parse_str_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        out = json.loads(raw)
        return [str(x) for x in out if isinstance(x, (str, int, float))]
    except Exception:  # noqa: BLE001
        return []


# --- Backward-compatible module-level helpers (default = IR profile) ---

_DEFAULT = IR_PROFILE


def is_iran_country(code: str | None) -> bool:
    return _DEFAULT.matches_country(code)


def is_iran_name(name: str | None) -> bool:
    return _DEFAULT.matches_name(name)


def is_iran_target(target: str | None) -> bool:
    return _DEFAULT.matches_target(target)


def is_iran_source(name: str | None, domain: str | None) -> bool:
    return _DEFAULT.matches_source(name, domain)


__all__ = [
    "is_country",
    "is_name",
    "is_target",
    "is_source",
    "parse_str_list",
    "is_iran_country",
    "is_iran_name",
    "is_iran_target",
    "is_iran_source",
]