"""Similarity — توابع خالص فاصله‌ی برداری وضعیت‌ها (Phase 20, اصلاح ممیزی).

- بردار وضعیت = ۹ سیگنال 0..1 به ترتیب ثابت `SIGNAL_ORDER`.
- متریک‌ها: `euclidean` (پیش‌فرض، روی مقادیر خام — اختلاف سطح مهم است)
  و `cosine` (روی مقادیر **مرکزدهی‌شده حول 0.5** — نقطه‌ی خنثی دامنه).
- چرا مرکزدهی؟ چون همه‌ی سیگنال‌ها نامنفی‌اند، cosine روی مقادیر خام فقط
  «جهت» را می‌سنجد و دو وضعیت با سطح متفاوت اما جهت مشابه را یکسان
  می‌بیند (مثلاً همه 0.5 در برابر همه 0.6). مرکزدهی این سوگیری را حذف می‌کند.
- بردار مرکزدهی‌شده‌ی صفر/نزدیک صفر (وضعیت کاملاً خنثی) جهت ندارد:
  خنثی↔خنثی → فاصله 0؛ خنثی↔جهت‌دار → فاصله 1.0 (نبود اطلاعات جهت،
  نه شباهت گمراه‌کننده؛ NaN هرگز تولید نمی‌شود).
- شباهت در [0, 1]: اقلیدسی `1/(1+d)`، کسینوسی `1 - d/2`.
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

N_DIMS = len(SIGNAL_ORDER)

# نقطه‌ی خنثی دامنه‌ی سیگنال‌ها؛ مبنای مرکزدهی cosine
NEUTRAL = 0.5
# آستانه‌ی «بردار عملاً صفر» برای حالت خنثی
NEAR_ZERO_EPS = 1e-9


def to_vector(signals: dict) -> list[float]:
    """بردار ۹تایی از دیکشنری سیگنال‌ها (None → 0.5 خنثی)."""
    out: list[float] = []
    for name in SIGNAL_ORDER:
        v = signals.get(name)
        out.append(float(v) if v is not None else NEUTRAL)
    return out


def center(vec: list[float]) -> list[float]:
    """مرکزدهی حول نقطه‌ی خنثی برای مقایسه‌ی جهتی."""
    return [v - NEUTRAL for v in vec]


def _norm(vec: list[float]) -> float:
    return math.sqrt(sum(v * v for v in vec))


def euclidean(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def normalize_euclidean(distance: float, n_compared: int) -> float:
    """نرمال‌سازی فاصله‌ی اقلیدسی به معادل تمام‌بعدی.

    وقتی فقط n بُعد از N_DIMS مقایسه شده، فاصله در فضای کوچک‌تر ذاتاً
    کوچک‌تر است؛ ضریب sqrt(N_DIMS/n) آن را به مقیاس کامل برمی‌گرداند تا
    snapshotهایی با پوشش متفاوت منصفانه رتبه‌بندی شوند.
    """
    if n_compared <= 0:
        raise ValueError("n_compared must be positive")
    if n_compared >= N_DIMS:
        return distance
    return distance * math.sqrt(N_DIMS / n_compared)


def cosine_distance(a: list[float], b: list[float]) -> float:
    """فاصله‌ی کسینوسی روی بردارهای **مرکزدهی‌شده** (در [0, 2]).

    مرکزدهی داخل همین تابع انجام می‌شود تا استفاده‌ی نادرست ناممکن باشد.
    """
    ca, cb = center(a), center(b)
    na, nb = _norm(ca), _norm(cb)
    if na <= NEAR_ZERO_EPS and nb <= NEAR_ZERO_EPS:
        return 0.0
    if na <= NEAR_ZERO_EPS or nb <= NEAR_ZERO_EPS:
        return 1.0
    cos = max(-1.0, min(1.0, sum(x * y for x, y in zip(ca, cb, strict=True)) / (na * nb)))
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


def masked_deltas(
    names: list[str], current: list[float], other: list[float]
) -> dict[str, float]:
    """واگرایی فقط روی ابعاد مقایسه‌شده (نام‌ها + زیربردارهای هم‌طول)."""
    return {
        name: round(o - c, 4)
        for name, c, o in zip(names, current, other, strict=True)
    }


__all__ = [
    "NEAR_ZERO_EPS",
    "NEUTRAL",
    "N_DIMS",
    "SIGNAL_ORDER",
    "center",
    "cosine_distance",
    "deltas",
    "euclidean",
    "masked_deltas",
    "normalize_euclidean",
    "similarity",
    "to_vector",
]
