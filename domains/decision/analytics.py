"""Analytics — توابع خالص موتور تصمیم (Phase 32).

قرارداد (v1, مستند و ثابت):
- bias جهت‌دار از چولگی سناریو:
  bias = ((bull − base) − (base − bear)) / max(|base|, eps) محدود به [−1, 1].
  سناریوی متقارن → bias صفر (بدون جهت).
- penalty ریسک = بیشینه‌ی ریسک‌های ورودی (مقیدکننده‌ترین).
- score = bias × (1 − penalty) در [−1, 1].
- decision:
  penalty ≥ 0.75 → avoid (ریسک حاکم است، مستقل از جهت)
  score ≥ 0.3 → accumulate | score ≤ ‎-0.3 → reduce | وگرنه hold.
- confidence: 0.8 با ریسک واقعی، 0.5 بدون داده‌ی ریسک (اعلام‌شده)،
  هر ورودی تهی یک پله کم می‌کند (کمینه 0.2).
- بدون AI؛ فقط ریاضیات قطعی.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DecisionScores:
    bias: float
    penalty: float
    score: float
    decision: str
    direction: str
    confidence: float
    reasons: list[str] = field(default_factory=list)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def directional_bias(base: float, bull: float, bear: float) -> float:
    denom = abs(base) if abs(base) > 1e-9 else 1e-9
    return _clamp(((bull - base) - (base - bear)) / denom, -1.0, 1.0)


def decide(
    *,
    base: float,
    bull: float,
    bear: float,
    risks: list[tuple[str, float]],
    tail: float | None = None,
) -> DecisionScores:
    """تصمیم از چولگی سناریو و سقف ریسک."""
    reasons: list[str] = []
    bias = directional_bias(base, bull, bear)
    penalty = max((r for _, r in risks), default=0.0)
    penalty = _clamp(penalty, 0.0, 1.0)
    score = round(bias * (1.0 - penalty), 4)

    if penalty >= 0.75:
        decision = "avoid"
        reasons.append(f"risk penalty {penalty:.2f} dominates direction")
    elif score >= 0.3:
        decision = "accumulate"
    elif score <= -0.3:
        decision = "reduce"
    else:
        decision = "hold"

    direction = "up" if bias > 0.05 else ("down" if bias < -0.05 else "flat")
    if risks:
        top = sorted(risks, key=lambda t: t[1], reverse=True)[:2]
        reasons.extend(f"top risk: {name}={value:.2f}" for name, value in top)
    else:
        reasons.append("no risk inputs; penalty assumed 0")
    if tail is not None:
        reasons.append(f"tail scenario at {tail}")

    conf = 0.8 if risks else 0.5
    return DecisionScores(
        bias=round(bias, 4),
        penalty=round(penalty, 4),
        score=score,
        decision=decision,
        direction=direction,
        confidence=conf,
        reasons=reasons,
    )


__all__ = ["DecisionScores", "decide", "directional_bias"]
