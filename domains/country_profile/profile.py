"""CountryProfile — پروفایل قابل تنظیم برای یک کشور (Stage 99).

فیلدها:
- code: کد کشور (مثلاً IR، CN)
- country_codes: کدهای قابل قبول (IR/IRN)
- name_keywords: کلمات کلیدی نام (iran/iranian)
- target_keywords: کلمات کلیدی هدف/دارایی (irn/iran)
- source_domain_suffixes: پسوندهای دامنهٔ منبع (.ir)
- macro_country_code: کد کشور در macro (IRN)
- languages: زبان‌های مرتبط
- assets: دارایی‌ها/نمادهای مرتبط
- transmission_channels: کانال‌های انتقال ریسک
- weights: وزن‌های تحلیلی
- report_settings: تنظیمات گزارش
- version: نسخهٔ پروفایل (در خروجی‌های مهم ثبت می‌شود)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CountryProfile:
    code: str
    country_codes: frozenset[str]
    name_keywords: frozenset[str]
    target_keywords: tuple[str, ...]
    source_domain_suffixes: tuple[str, ...]
    macro_country_code: str
    languages: tuple[str, ...] = field(default_factory=tuple)
    assets: tuple[str, ...] = field(default_factory=tuple)
    transmission_channels: tuple[str, ...] = field(default_factory=tuple)
    weights: dict = field(default_factory=dict)
    report_settings: dict = field(default_factory=dict)
    version: str = "v1"

    def matches_country(self, code: str | None) -> bool:
        return bool(code) and code.strip().upper() in self.country_codes

    def matches_name(self, name: str | None) -> bool:
        if not name:
            return False
        words = set(name.strip().casefold().replace("-", " ").split())
        return bool(words & {k.casefold() for k in self.name_keywords})

    def matches_target(self, target: str | None) -> bool:
        if not target:
            return False
        low = target.casefold()
        return any(kw in low for kw in self.target_keywords)

    def matches_source(self, name: str | None, domain: str | None) -> bool:
        if self.matches_name(name):
            return True
        if domain:
            low = domain.strip().casefold()
            for suf in self.source_domain_suffixes:
                if low.endswith(suf.casefold()):
                    return True
        return False

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "country_codes": sorted(self.country_codes),
            "name_keywords": sorted(self.name_keywords),
            "target_keywords": list(self.target_keywords),
            "source_domain_suffixes": list(self.source_domain_suffixes),
            "macro_country_code": self.macro_country_code,
            "languages": list(self.languages),
            "assets": list(self.assets),
            "transmission_channels": list(self.transmission_channels),
            "weights": dict(self.weights),
            "report_settings": dict(self.report_settings),
            "version": self.version,
        }