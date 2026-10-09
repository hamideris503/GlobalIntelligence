"""Analytics — توابع خالص موتور ریسک (Phase 31).

قرارداد (v1, مستند و ثابت):
- هر دسته از یک یا چند ورودی 0..1 ساخته می‌شود:
  - inflation_risk = فشار تورمی
  - growth_risk = |رشد − 0.5| × 2 (هر دو دم: رکود و overheat)
  - market_risk = استرس مالی
  - energy_risk = ریسک انرژی
  - geopolitical_risk = بیشینه‌ی (ریسک جهان، تنش بازیگران)
  - trade_risk = ریسک تجاری
  - social_risk = فشار اجتماعی
  - uncertainty = میانگین گستردگی سناریو ((bull−bear)/|base| محدود به [0,1])
- ورودی ناموجود → دسته skip می‌شود (نه 0.5 جعلی)؛ حداقل ۱ ورودی لازم است.
- level: <0.25 low | <0.5 medium | <0.75 high | وگرنه critical.
- confidence = میانگین اعتماد ورودی‌ها.
- بدون AI؛ فقط ریاضیات قطعی.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RiskScore:
    score: float
    level: str
    confidence: float
    drivers: list[str] = field(default_factory=list)
    method: str = "risk_v1"


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def level_for(score: float) -> str:
    if score < 0.25:
        return "low"
    if score < 0.5:
        return "medium"
    if score < 0.75:
        return "high"
    return "critical"


def combine(parts: list[tuple[float, float, str]], mode: str = "mean") -> RiskScore | None:
    """ترکیب اجزا (value, confidence, driver)؛ تهی → None.

    mode: mean (میانگین) یا max (بیشینه؛ برای geopolitical).
    """
    if not parts:
        return None
    if mode == "max":
        value, conf, driver = max(parts, key=lambda p: p[0])
        score, drivers = value, [driver]
    else:
        score = sum(v for v, _, _ in parts) / len(parts)
        conf = sum(c for _, c, _ in parts) / len(parts)
        drivers = [d for _, _, d in parts]
    score = _clamp01(score)
    return RiskScore(
        score=round(score, 4),
        level=level_for(score),
        confidence=round(conf, 4),
        drivers=drivers,
    )


def growth_risk(growth: float | None, conf: float = 0.5) -> RiskScore | None:
    if growth is None:
        return None
    return combine([(abs(growth - 0.5) * 2.0, conf, "growth_deviation")])


def spread_uncertainty(spreads: list[float]) -> RiskScore | None:
    """عدم‌قطعیت از گستردگی سناریوها (bull−bear)/|base|."""
    vals = [_clamp01(s) for s in spreads if s is not None]
    if not vals:
        return None
    mean = sum(vals) / len(vals)
    return RiskScore(
        score=round(mean, 4),
        level=level_for(mean),
        confidence=0.5,
        drivers=["scenario_spread"],
    )


__all__ = [
    "RiskScore",
    "combine",
    "growth_risk",
    "level_for",
    "spread_uncertainty",
]
