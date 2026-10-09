"""Matching — قواعد تطبیق ایران (Phase 33).

یک رکورد «مرتبط با ایران» است اگر هر یک برقرار باشد (v1, مستند):
- کد کشور: IR / IRN (/article.country، macro.country).
- نام بازیگر/موجودیت/موضوع حاوی iran/iranian (case-insensitive).
- هدف (target/asset) حاوی IRN یا Iran.
- منبع با دامنه‌ی .ir یا نام حاوی iran.

بدون AI؛ فقط تطبیق رشته‌ای قطعی.
"""
from __future__ import annotations

import json

COUNTRY_CODES = frozenset({"IR", "IRN"})
NAME_KEYWORDS = frozenset({"iran", "iranian"})


def _norm(text: str) -> str:
    return " ".join(text.strip().split()).casefold()


def is_iran_country(code: str | None) -> bool:
    return bool(code) and code.strip().upper() in COUNTRY_CODES


def is_iran_name(name: str | None) -> bool:
    if not name:
        return False
    words = set(_norm(name).replace("-", " ").split())
    return bool(words & NAME_KEYWORDS)


def is_iran_target(target: str | None) -> bool:
    if not target:
        return False
    low = target.casefold()
    return "irn" in low or "iran" in low


def is_iran_source(name: str | None, domain: str | None) -> bool:
    if is_iran_name(name):
        return True
    if domain and domain.strip().casefold().endswith(".ir"):
        return True
    return False


def parse_str_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        out = json.loads(raw)
        return [str(x) for x in out if isinstance(x, (str, int, float))]
    except Exception:  # noqa: BLE001
        return []


__all__ = [
    "COUNTRY_CODES",
    "NAME_KEYWORDS",
    "is_iran_country",
    "is_iran_name",
    "is_iran_source",
    "is_iran_target",
    "parse_str_list",
]
