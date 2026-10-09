"""Analytics — توابع خالص هوشمندی پورتفوی (Phase 35).

قرارداد (v1, مستند و ثابت):
- وزن‌ها نرمال می‌شوند (جمع → ۱)؛ جمع صفر/نامعتبر → خطا (نه حدس).
- expected_return = میانگین وزنی base سناریوهای پوشش‌یافته،
  نرمال‌شده بر وزن پوشش‌یافته (بازده «بخش پوشش‌یافته» + coverage جداگانه).
  (هشدار صادقانه: فقط برای موقعیت‌های هم‌واحد معنادار است؛ در ترکیب
  واحدها، جزئیات هر موقعیت در detail مبنای تفسیر است.)
- spread هر موقعیت = (bull−bear)/|base|؛ uncertainty = میانگین وزنی spreadها.
- concentration = هرفیندال Σw² روی وزن‌های نرمال؛ diversification = ‎1 − تمرکز.
- coverage = سهم وزن دارای مجموعه‌ی سناریوی کامل؛ پوشش صفر → None کلی.
- confidence: 0.4 + 0.4×coverage (۰.۴ تا ۰.۸).
- بدون AI؛ فقط ریاضیات قطعی.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PositionInput:
    target: str
    weight: float
    base: float | None
    bull: float | None
    bear: float | None


@dataclass(frozen=True)
class PortfolioStats:
    expected_return: float
    uncertainty: float
    concentration: float
    diversification: float
    coverage: float
    confidence: float
    detail: list[dict] = field(default_factory=list)
    method: str = "portfolio_v1"


def normalize_weights(positions: dict[str, float]) -> dict[str, float]:
    """نرمال‌سازی وزن‌ها؛ جمع صفر/منفی/تهی → ValueError."""
    clean = {t: float(w) for t, w in positions.items() if w is not None}
    total = sum(clean.values())
    if not clean or total <= 0:
        raise ValueError("positions must have positive total weight")
    return {t: round(w / total, 6) for t, w in clean.items()}


def spread_of(base: float | None, bull: float | None, bear: float | None) -> float | None:
    if base is None or bull is None or bear is None or base == 0:
        return None
    return abs(bull - bear) / abs(base)


def analyze_positions(weights: dict[str, float], scenarios: dict[str, dict]) -> PortfolioStats | None:
    """تحلیل پورتفوی؛ پوشش صفر → None."""
    norm = normalize_weights(weights)
    detail: list[dict] = []
    covered_w = 0.0
    ret_acc = 0.0
    unc_acc = 0.0
    for target, w in norm.items():
        s = scenarios.get(target, {})
        base, bull, bear = s.get("base"), s.get("bull"), s.get("bear")
        spread = spread_of(base, bull, bear)
        if base is not None and spread is not None:
            ret_acc += w * base
            unc_acc += w * spread
            covered_w += w
            detail.append(
                {
                    "target": target,
                    "weight": w,
                    "base": base,
                    "spread": round(spread, 6),
                    "contribution": round(w * base, 6),
                }
            )
        else:
            detail.append({"target": target, "weight": w, "uncovered": True})
    if covered_w <= 0:
        return None
    concentration = round(sum(w * w for w in norm.values()), 6)
    coverage = round(covered_w, 6)
    return PortfolioStats(
        expected_return=round(ret_acc / covered_w, 6),
        uncertainty=round(min(1.0, unc_acc / covered_w), 6),
        concentration=concentration,
        diversification=round(1.0 - concentration, 6),
        coverage=coverage,
        confidence=round(0.4 + 0.4 * coverage, 4),
        detail=detail,
    )


__all__ = [
    "PortfolioStats",
    "PositionInput",
    "analyze_positions",
    "normalize_weights",
    "spread_of",
]
