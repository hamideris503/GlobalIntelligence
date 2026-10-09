"""Analytics — توابع خالص تحلیل سری macro (Phase 21).

قرارداد (v1, مستند و ثابت):
- ورودی: مقادیر مرتب نزولی دوره (جدیدترین اول).
- yoy: تغییر کسری دو مشاهده‌ی آخر؛ نیازمند ۲ مقدار مثبت-غیرصفر.
- acceleration: اختلاف yoy جاری و قبلی؛ نیازمند ۳ مقدار.
- z_score: انحراف معیارشده‌ی آخرین مقدار نسبت به کل تاریخچه؛ نیازمند ≥۳ نقطه
  و انحراف معیار مثبت (وگرنه None — نه صفر جعلی).
- momentum: clamp(z/2) در [-1, 1]؛ برچسب از آستانه‌های z:
  z ≥ 1 → accelerating | z ≤ ‎-1 → decelerating | وگرنه stable.
- confidence: 0.4 برای ۲ نقطه، 0.6 برای ۳–۴، 0.8 برای ≥۵.
- بدون AI؛ فقط ریاضیات قطعی.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


@dataclass(frozen=True)
class SeriesStats:
    n: int
    latest: float | None
    yoy: float | None
    acceleration: float | None
    z_score: float | None
    momentum: float | None
    momentum_label: str
    confidence: float
    method: str = "series_stats_v1"


def _clean(values_desc: list[float | None]) -> list[float]:
    return [v for v in values_desc if v is not None]


def yoy(values_desc: list[float | None]) -> float | None:
    vals = _clean(values_desc)[:2]
    if len(vals) < 2 or not vals[1]:
        return None
    return (vals[0] - vals[1]) / abs(vals[1])


def acceleration(values_desc: list[float | None]) -> float | None:
    vals = _clean(values_desc)[:3]
    if len(vals) < 3 or not vals[1] or not vals[2]:
        return None
    yoy_now = (vals[0] - vals[1]) / abs(vals[1])
    yoy_prev = (vals[1] - vals[2]) / abs(vals[2])
    return yoy_now - yoy_prev


def z_score(values_desc: list[float | None]) -> float | None:
    vals = _clean(values_desc)
    if len(vals) < 3:
        return None
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    if var <= 0.0:
        return None
    return (vals[0] - mean) / math.sqrt(var)


def momentum_label(z: float | None) -> str:
    if z is None:
        return "unknown"
    if z >= 1.0:
        return "accelerating"
    if z <= -1.0:
        return "decelerating"
    return "stable"


def confidence_for(n: int) -> float:
    if n >= 5:
        return 0.8
    if n >= 3:
        return 0.6
    if n >= 2:
        return 0.4
    return 0.1


def analyze_series(values_desc: list[float | None]) -> SeriesStats:
    """تحلیل کامل یک سری مرتب نزولی."""
    vals = _clean(values_desc)
    n = len(vals)
    if n == 0:
        return SeriesStats(
            n=0, latest=None, yoy=None, acceleration=None, z_score=None,
            momentum=None, momentum_label="unknown", confidence=0.1,
        )
    z = z_score(values_desc)
    mom = round(_clamp(z / 2.0, -1.0, 1.0), 4) if z is not None else None
    return SeriesStats(
        n=n,
        latest=vals[0],
        yoy=yoy(values_desc),
        acceleration=acceleration(values_desc),
        z_score=round(z, 4) if z is not None else None,
        momentum=mom,
        momentum_label=momentum_label(z),
        confidence=confidence_for(n),
    )


__all__ = [
    "SeriesStats",
    "acceleration",
    "analyze_series",
    "confidence_for",
    "momentum_label",
    "yoy",
    "z_score",
]
