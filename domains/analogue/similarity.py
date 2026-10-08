"""Similarity — توابع خالص فاصله‌ی برداری وضعیت‌ها (Phase 20).

- بردار وضعیت = ۹ سیگنال 0..1 به ترتیب ثابت `SIGNAL_ORDER`.
- متریک‌ها: `euclidean` (پیش‌فرض) و `cosine`.
- شباهت در [0, 1]: برای اقلیدسی `1/(1+d)`، برای کسینوسی `(cos+1)/2`.
- بدون AI؛ فقط ریاضیات قطعی.
"""
from __future__ import annotations

import math

SIGNAL_ORDER = [
    "growth_pressure",
    "inflation_pressure",
    "liquidity",
    "financial_stress",
    "geopolitical_risk",
    "energy_risk",
    "trade_risk",
    "political_risk",
    "social_pressure",
]


def to_vector(signals: dict) -> list[float]:
    """بردار ۹تایی از دیکشنری سیگنال‌ها (None → 0.5 خنثی)."""
    out: list[float] = []
    for name in SIGNAL_ORDER:
        v = signals.get(name)
        out.append(float(v) if v is not None else 0.5)
    return out


def euclidean(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 1.0
    cos = max(-1.0, min(1.0, dot / (na * nb)))
    return 1.0 - cos


def similarity(distance: float, metric: str) -> float:
    """تبدیل فاصله به شباهت [0, 1]."""
    if metric == "cosine":
        # cosine_distance در [0, 2] است
        return round(max(0.0, min(1.0, 1.0 - distance / 2.0)), 4)
    return round(1.0 / (1.0 + distance), 4)


def deltas(current: list[float], other: list[float]) -> dict[str, float]:
    """اختلاف هر سیگنال (other - current) برای تفسیر واگرایی."""
    return {
        name: round(o - c, 4)
        for name, c, o in zip(SIGNAL_ORDER, current, other, strict=True)
    }


__all__ = [
    "SIGNAL_ORDER",
    "cosine_distance",
    "deltas",
    "euclidean",
    "similarity",
    "to_vector",
]
