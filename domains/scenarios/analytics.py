"""Scenario math — توابع خالص سناریوسازی (Phase 30).

قرارداد (v1, مستند و ثابت):
- سناریوها جهت‌مقداری‌اند، نه رفاهی: bull = مقادیر بالاتر، bear = پایین‌تر،
  tail = دم چپ (‎-2σ). دم راست در آینده اضافه می‌شود.
- واحد شوک σ = انحراف معیار جامعه‌ی سری؛ نیازمند ≥۳ نقطه و واریانس مثبت.
- اگر σ ناموجود باشد، سناریو ساخته نمی‌شود (نه شوک حدسی) — فقط base می‌ماند.
- bull/bear = expected ± σ؛ tail = expected − 2σ.
- confidence: base × 1.0، bull/bear × 0.9، tail × 0.7 (تخفیف مستند عدم‌قطعیت).
- بازه از base کپی می‌شود (ساده‌سازی ثبت‌شده در assumptions).
- بدون AI؛ فقط ریاضیات قطعی.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

SCENARIOS = ("base", "bull", "bear", "tail")
CONFIDENCE_DISCOUNT = {"base": 1.0, "bull": 0.9, "bear": 0.9, "tail": 0.7}


@dataclass(frozen=True)
class ScenarioSet:
    base: float
    sigma: float
    values: dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"base": self.base, "sigma": self.sigma, "values": self.values}


def series_sigma(values_oldest_first: list[float | None]) -> float | None:
    """انحراف معیار جامعه؛ نیازمند ≥۳ نقطه و واریانس مثبت."""
    vals = [v for v in values_oldest_first if v is not None]
    if len(vals) < 3:
        return None
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    if var <= 0.0:
        return None
    return math.sqrt(var)


def build_scenarios(expected: float, sigma: float | None) -> ScenarioSet | None:
    """مجموعه‌ی ۴ سناریو؛ sigma ناموجود → None (فقط base)."""
    if sigma is None:
        return None
    values = {
        "base": round(expected, 6),
        "bull": round(expected + sigma, 6),
        "bear": round(expected - sigma, 6),
        "tail": round(expected - 2.0 * sigma, 6),
    }
    return ScenarioSet(base=round(expected, 6), sigma=round(sigma, 6), values=values)


__all__ = [
    "CONFIDENCE_DISCOUNT",
    "SCENARIOS",
    "ScenarioSet",
    "build_scenarios",
    "series_sigma",
]
