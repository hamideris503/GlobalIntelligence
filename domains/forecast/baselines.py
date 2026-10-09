"""Baselines — پیش‌بینی‌کننده‌های پایه‌ی قطعی (Phase 25).

طبق ROADMAP ابتدا Baselineها، سپس مدل‌های پیشرفته (فازهای بعد).
هر سه قطعی و بدون AI هستند:

- naive: مقدار آخر (نیازمند ≥۱ نقطه).
- historical_mean: میانگین تاریخچه (نیازمند ≥۲ نقطه).
- random_walk: آخرین مقدار + رانش میانگین تفاضل‌ها (نیازمند ≥۲ نقطه).

بازه‌ی اطمینان v1 (مستند و ساده‌شده): ±1.96×انحراف معیار گام‌به‌گام
درون‌نمونه‌ای؛ نیازمند ≥۳ نقطه و واریانس مثبت، وگرنه بازه None
(نه بازه‌ی جعلی). گسترش بازه با افق در v1 لحاظ نشده و ثبت می‌شود.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BaselineResult:
    expected_value: float
    interval_low: float | None
    interval_high: float | None
    confidence: float
    method: str


def _clean(values_oldest_first: list[float | None]) -> list[float]:
    return [v for v in values_oldest_first if v is not None]


def _step_std(vals: list[float]) -> float | None:
    """انحراف معیار تفاضل‌های گام‌به‌گام؛ نیازمند ≥۳ نقطه و واریانس مثبت."""
    if len(vals) < 3:
        return None
    diffs = [b - a for a, b in zip(vals, vals[1:], strict=False)]
    mean = sum(diffs) / len(diffs)
    var = sum((d - mean) ** 2 for d in diffs) / len(diffs)
    if var <= 0.0:
        return None
    return math.sqrt(var)


def _interval(last: float, std: float | None) -> tuple[float | None, float | None]:
    if std is None:
        return None, None
    half = 1.96 * std
    return round(last - half, 6), round(last + half, 6)


def naive(values_oldest_first: list[float | None]) -> BaselineResult | None:
    vals = _clean(values_oldest_first)
    if not vals:
        return None
    last = vals[-1]
    lo, hi = _interval(last, _step_std(vals))
    return BaselineResult(
        expected_value=last,
        interval_low=lo,
        interval_high=hi,
        confidence=0.3 if len(vals) < 3 else 0.5,
        method="baseline_naive_v1",
    )


def historical_mean(values_oldest_first: list[float | None]) -> BaselineResult | None:
    vals = _clean(values_oldest_first)
    if len(vals) < 2:
        return None
    mean = sum(vals) / len(vals)
    lo, hi = _interval(mean, _step_std(vals))
    return BaselineResult(
        expected_value=round(mean, 6),
        interval_low=lo,
        interval_high=hi,
        confidence=0.4 if len(vals) < 5 else 0.6,
        method="baseline_mean_v1",
    )


def random_walk(
    values_oldest_first: list[float | None], steps: int = 1
) -> BaselineResult | None:
    vals = _clean(values_oldest_first)
    if len(vals) < 2:
        return None
    diffs = [b - a for a, b in zip(vals, vals[1:], strict=False)]
    drift = sum(diffs) / len(diffs)
    expected = vals[-1] + drift * max(1, steps)
    lo, hi = _interval(expected, _step_std(vals))
    return BaselineResult(
        expected_value=round(expected, 6),
        interval_low=lo,
        interval_high=hi,
        confidence=0.4 if len(vals) < 5 else 0.6,
        method="baseline_rw_v1",
    )


METHODS = {
    "naive": naive,
    "historical_mean": historical_mean,
    "random_walk": random_walk,
}

__all__ = ["BaselineResult", "METHODS", "historical_mean", "naive", "random_walk"]
