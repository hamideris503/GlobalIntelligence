"""Tri-state screening decision engine (F04.1).

Combines Kev/Laya probabilities (and optional deterministic rules) into one of:
  RELEVANT   -> enter analysis pipeline
  IRRELEVANT -> keep in archive, skip heavy analysis
  UNCERTAIN  -> route to re-review queue (never silently dropped)

Safety invariants:
  * Runtime errors / timeouts / missing models -> UNCERTAIN (never IRRELEVANT).
  * Model disagreement beyond a threshold -> UNCERTAIN.
  * Low confidence -> UNCERTAIN.
  * Rules/model conflict -> UNCERTAIN.
  * RELEVANCE is kept separate from PRIORITY (P0-P4).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ScreeningVerdict(str, Enum):
    RELEVANT = "relevant"
    IRRELEVANT = "irrelevant"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class DecisionResult:
    verdict: ScreeningVerdict
    reason: str
    probability: float | None
    confidence: float | None
    kev_probability: float | None
    laya_probability: float | None


def _as_prob(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return None
    v = float(value)
    if not (0.0 <= v <= 1.0):
        return None
    import math
    if not math.isfinite(v):
        return None
    return v


def decide(
    *,
    kev_probability: Any = None,
    laya_probability: Any = None,
    rules_relevant: bool | None = None,
    kev_ok: bool = True,
    laya_ok: bool = True,
    runtime_error: bool = False,
    timeout: bool = False,
    confidence_threshold: float = 0.8,
    disagreement_threshold: float = 0.3,
) -> DecisionResult:
    """Return a tri-state verdict. Never raises."""
    kp = _as_prob(kev_probability)
    lp = _as_prob(laya_probability)

    # Safety: runtime problems never become IRRELEVANT.
    if runtime_error or timeout or not kev_ok or not laya_ok:
        return DecisionResult(
            verdict=ScreeningVerdict.UNCERTAIN,
            reason="runtime_error_or_timeout",
            probability=None,
            confidence=None,
            kev_probability=kp,
            laya_probability=lp,
        )

    probs = [p for p in (kp, lp) if p is not None]
    if not probs:
        return DecisionResult(
            verdict=ScreeningVerdict.UNCERTAIN,
            reason="no_model_output",
            probability=None,
            confidence=None,
            kev_probability=kp,
            laya_probability=lp,
        )

    # Model disagreement -> UNCERTAIN (re-review).
    if kp is not None and lp is not None and abs(kp - lp) >= disagreement_threshold:
        avg = (kp + lp) / 2.0
        return DecisionResult(
            verdict=ScreeningVerdict.UNCERTAIN,
            reason="model_disagreement",
            probability=avg,
            confidence=max(avg, 1.0 - avg),
            kev_probability=kp,
            laya_probability=lp,
        )

    avg = sum(probs) / len(probs)
    confidence = max(avg, 1.0 - avg)

    # Low confidence -> UNCERTAIN.
    if confidence < confidence_threshold:
        return DecisionResult(
            verdict=ScreeningVerdict.UNCERTAIN,
            reason="low_confidence",
            probability=avg,
            confidence=confidence,
            kev_probability=kp,
            laya_probability=lp,
        )

    # Rules/model conflict -> UNCERTAIN.
    if rules_relevant is True and avg < 0.5:
        return DecisionResult(
            verdict=ScreeningVerdict.UNCERTAIN,
            reason="rules_model_conflict",
            probability=avg,
            confidence=confidence,
            kev_probability=kp,
            laya_probability=lp,
        )
    if rules_relevant is False and avg >= 0.5:
        return DecisionResult(
            verdict=ScreeningVerdict.UNCERTAIN,
            reason="rules_model_conflict",
            probability=avg,
            confidence=confidence,
            kev_probability=kp,
            laya_probability=lp,
        )

    verdict = ScreeningVerdict.RELEVANT if avg >= 0.5 else ScreeningVerdict.IRRELEVANT
    return DecisionResult(
        verdict=verdict,
        reason="decided",
        probability=avg,
        confidence=confidence,
        kev_probability=kp,
        laya_probability=lp,
    )