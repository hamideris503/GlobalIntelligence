"""Learners — توابع خالص یادگیری از تاریخچه (Phase 51).

قرارداد (v1, مستند و ثابت):
- trend: شیب حداقل‌مربعات MAE روی دوره‌ها (نیازمند ≥۳ نقطه)؛
  شیب < 0 → improving | > 0 → degrading | وگرنه stable (تلرانس 1e-9).
  confidence: ۰.۵ برای ۳ نقطه، ‎+0.1 به‌ازای هر نقطه‌ی اضافه تا سقف ۰.۹.
- base_rate: فراوانی هر رژیم در تاریخچه (جمع = ۱).
- threshold_p90: چندک ۹۰ مقادیر یک سیگنال (نیازمند ≥۵ نقطه)؛
  پیشنهاد آستانه‌ی داده‌محور برای هشدار.
- نمونه‌ی ناکافی → None (نه حدس). بدون AI.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TrendResult:
    direction: str
    slope: float
    n_points: int
    confidence: float


@dataclass(frozen=True)
class Insight:
    kind: str
    subject: str
    value: dict = field(default_factory=dict)
    confidence: float = 0.5
    method: str = "learning_v1"


def least_squares_slope(xs: list[float], ys: list[float]) -> float | None:
    """شیب رگرسیون خطی؛ نیازمند ≥۲ نقطه و واریانس x مثبت."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom <= 0:
        return None
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / denom


def accuracy_trend(maes: list[float | None]) -> TrendResult | None:
    """روند دقت یک مدل از تاریخچه‌ی MAE (قدیمی→جدید)."""
    vals = [m for m in maes if m is not None]
    if len(vals) < 3:
        return None
    slope = least_squares_slope([float(i) for i in range(len(vals))], vals)
    if slope is None:
        return None
    if slope < -1e-9:
        direction = "improving"
    elif slope > 1e-9:
        direction = "degrading"
    else:
        direction = "stable"
    confidence = round(min(0.9, 0.5 + 0.1 * (len(vals) - 3)), 2)
    return TrendResult(
        direction=direction, slope=round(slope, 6),
        n_points=len(vals), confidence=confidence,
    )


def base_rates(labels: list[str | None]) -> dict[str, float] | None:
    """فراوانی هر برچسب (تهی‌ها نادیده)؛ تهی کامل → None."""
    valid = [label for label in labels if label]
    if not valid:
        return None
    total = len(valid)
    out: dict[str, float] = {}
    for label in valid:
        out[label] = round(out.get(label, 0.0) + 1.0 / total, 4)
    return out


def threshold_p90(values: list[float | None]) -> float | None:
    """چندک ۹۰؛ نیازمند ≥۵ نقطه."""
    vals = sorted(v for v in values if v is not None)
    if len(vals) < 5:
        return None
    rank = 0.9 * (len(vals) - 1)
    lo, hi = int(rank), min(len(vals) - 1, int(rank) + 1)
    frac = rank - lo
    return round(vals[lo] * (1 - frac) + vals[hi] * frac, 4)


__all__ = [
    "Insight",
    "TrendResult",
    "accuracy_trend",
    "base_rates",
    "least_squares_slope",
    "threshold_p90",
]
