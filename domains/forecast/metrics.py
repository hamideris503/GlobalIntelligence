"""Metrics — توابع خالص ارزیابی پیش‌بینی (Phase 28).

قرارداد (v1, تعاریف استاندارد):
- abs_error = |expected - actual|؛ squared_error = مربع آن.
- MAE/RMSE روی مجموعه‌ی outcomeها (نیازمند ≥۱).
- brier = (p - y)² برای پیش‌بینی احتمالاتی (نیازمند probability و actual_bool).
- log_loss = -(y·ln p + (1-y)·ln(1-p)) با clip احتمال به [1e-6, 1-1e-6].
- calibration: دهک‌بندی احتمال پیش‌بینی‌شده در برابر فراوانی مشاهده‌شده.
- ورودی نامعتبر/ناکافی → None (نه عدد جعلی). بدون AI.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass(frozen=True)
class ValueScores:
    abs_error: float
    squared_error: float


@dataclass(frozen=True)
class ProbScores:
    brier_score: float
    log_loss: float


@dataclass(frozen=True)
class AggregateScores:
    n: int
    mae: float | None
    rmse: float | None
    mean_brier: float | None
    mean_log_loss: float | None
    calibration: list[dict] = field(default_factory=list)


def value_scores(expected: float, actual: float) -> ValueScores:
    err = abs(expected - actual)
    return ValueScores(abs_error=round(err, 6), squared_error=round(err * err, 6))


def prob_scores(probability: float, actual_bool: bool) -> ProbScores:
    p = _clamp01(probability)
    p = min(max(p, 1e-6), 1.0 - 1e-6)
    y = 1.0 if actual_bool else 0.0
    brier = (p - y) ** 2
    logloss = -(y * math.log(p) + (1.0 - y) * math.log(1.0 - p))
    return ProbScores(
        brier_score=round(brier, 6), log_loss=round(logloss, 6)
    )


def parse_bool(raw: str | None) -> bool | None:
    """actual_bool رشته‌ای ("true"/"false") → bool؛ نامعتبر → None."""
    if raw is None:
        return None
    v = raw.strip().lower()
    if v == "true":
        return True
    if v == "false":
        return False
    return None


def aggregate(
    abs_errors: list[float],
    squared_errors: list[float],
    briers: list[float],
    loglosses: list[float],
    prob_pairs: list[tuple[float, bool]],
    n_bins: int = 10,
) -> AggregateScores:
    """تجمیع روی مجموعه‌ی outcomeها."""
    n = len(abs_errors)
    mae = round(sum(abs_errors) / n, 6) if n else None
    rmse = (
        round(math.sqrt(sum(squared_errors) / n), 6) if n else None
    )
    mean_brier = round(sum(briers) / len(briers), 6) if briers else None
    mean_logloss = round(sum(loglosses) / len(loglosses), 6) if loglosses else None
    calibration = calibrate(prob_pairs, n_bins=n_bins)
    return AggregateScores(
        n=n,
        mae=mae,
        rmse=rmse,
        mean_brier=mean_brier,
        mean_log_loss=mean_logloss,
        calibration=calibration,
    )


def calibrate(
    prob_pairs: list[tuple[float, bool]], n_bins: int = 10
) -> list[dict]:
    """کالیبراسیون: هر دهک [میانگین پیش‌بینی، فراوانی مشاهده، تعداد]."""
    if not prob_pairs or n_bins < 1:
        return []
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for p, y in prob_pairs:
        idx = min(n_bins - 1, int(_clamp01(p) * n_bins))
        bins[idx].append((p, y))
    out = []
    for i, items in enumerate(bins):
        if not items:
            continue
        mean_p = sum(p for p, _ in items) / len(items)
        freq = sum(1 for _, y in items if y) / len(items)
        out.append(
            {
                "bin": f"{i / n_bins:.1f}-{(i + 1) / n_bins:.1f}",
                "mean_predicted": round(mean_p, 4),
                "observed_freq": round(freq, 4),
                "n": len(items),
            }
        )
    return out


__all__ = [
    "AggregateScores",
    "ProbScores",
    "ValueScores",
    "aggregate",
    "calibrate",
    "parse_bool",
    "prob_scores",
    "value_scores",
]
