"""Debate aggregation — قطعی، بدون LLM (Step 3).

- میانگین وزنی در فضای log-odds.
- وزن هر agent از Brier گذشته‌اش (model_performance) با shrinkage به وزن مساوی وقتی n<30.
- disagreement = انحراف معیار احتمال‌ها؛ confidence نهایی با اختلاف کم می‌شود.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

SHRINKAGE_N = 30


def _logit(p: float) -> float:
    p = min(0.999, max(0.001, p))
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


@dataclass
class AggregateResult:
    consensus_probability: float
    disagreement: float
    confidence: float
    weights: dict[str, float] = field(default_factory=dict)


def _brier_weights(probs: dict[str, float], briers: dict[str, tuple[float, int]]) -> dict[str, float]:
    """وزن از Brier: skill = max(0, 0.25 - brier)؛ shrinkage به وزن مساوی وقتی n کم است."""
    names = list(probs)
    if not names:
        return {}
    skills: dict[str, float] = {}
    for n in names:
        brier, cnt = briers.get(n, (0.25, 0))
        skill = max(0.0, 0.25 - float(brier))
        w = cnt / SHRINKAGE_N
        w = min(1.0, max(0.0, w))
        # ترکیب با وزن مساوی (shrinkage)
        skills[n] = w * skill + (1.0 - w) * (1.0 / len(names))
    total = sum(skills.values())
    if total <= 0:
        return {n: 1.0 / len(names) for n in names}
    return {n: s / total for n, s in skills.items()}


def aggregate(
    probs: dict[str, float],
    qualities: dict[str, float] | None = None,
    briers: dict[str, tuple[float, int]] | None = None,
) -> AggregateResult:
    """تجمیع قطعی."""
    if not probs:
        raise ValueError("no agent probabilities to aggregate")
    qualities = qualities or {}
    briers = briers or {}
    weights = _brier_weights(probs, briers)
    # کیفیت (ارجاع جعلی و...) به‌صورت ضربی اعمال می‌شود
    adj = {n: weights[n] * qualities.get(n, 1.0) for n in probs}
    total = sum(adj.values())
    if total <= 0:
        adj = {n: 1.0 / len(probs) for n in probs}
        total = 1.0
    adj = {n: w / total for n, w in adj.items()}

    mean_logit = sum(adj[n] * _logit(p) for n, p in probs.items())
    consensus = _sigmoid(mean_logit)
    mean_p = sum(probs.values()) / len(probs)
    disagreement = math.sqrt(sum((p - mean_p) ** 2 for p in probs.values()) / len(probs))
    # confidence: میانگین کیفیت منهای جریمه‌ی اختلاف
    avg_q = sum(qualities.get(n, 1.0) for n in probs) / len(probs)
    confidence = max(0.0, min(1.0, avg_q * (1.0 - min(1.0, disagreement * 2.0))))
    return AggregateResult(
        consensus_probability=round(consensus, 4),
        disagreement=round(disagreement, 4),
        confidence=round(confidence, 4),
        weights={n: round(w, 4) for n, w in adj.items()},
    )


def quant_anchor_probability(baselines: dict, reference_price: float | None) -> float:
    """لنگر آماری بدون LLM: میانگین expected baselineها در برابر قیمت مرجع.

    ملایم حول ۰.۵ تا لنگر غلبه نکند؛ بدون مرجع یا baseline → خنثی ۰.۵.
    """
    if reference_price is None:
        return 0.5
    exps = [
        float(b["expected_value"]) for b in (baselines or {}).values()
        if b.get("expected_value") is not None
    ]
    if not exps:
        return 0.5
    mean_exp = sum(exps) / len(exps)
    if mean_exp > reference_price:
        return 0.55
    if mean_exp < reference_price:
        return 0.45
    return 0.5
