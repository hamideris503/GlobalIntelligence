"""Checks — چک‌های خالص خودارزیابی (Phase 39).

قرارداد (v1, آستانه‌های مستند و ثابت):
- هر چک → (status, value, detail) با status در {pass, warn, fail}.
- classification: نسبت done؛ ‎≥0.9 pass | ‎≥0.5 warn | وگرنه fail (بدون مقاله: warn).
- evidence: پوشش claim دارای evidence؛ ‎≥0.8 pass | ‎≥0.5 warn | وگرنه fail.
- forecast: وجود حداقل یک مدل امتیازدار → pass، وگرنه warn (نه fail؛ چرخه‌ی طبیعی).
- freshness: ساعت از آخرین مشاهده‌ی market؛ ‎≤72 pass | ‎≤168 warn | وگرنه fail؛ بدون داده → warn.
- memory: هر ۳ لایه‌ی raw/event/state موجود → pass؛ هر غایبی → warn.
- graph: روابط > 0 → pass، وگرنه warn.
- نمره: pass=1، warn=0.5، fail=0؛ grade: ‎≥0.9 A | ‎≥0.7 B | ‎≥0.5 C | وگرنه D.
- بدون AI؛ فقط ریاضیات قطعی.
"""
from __future__ import annotations

from dataclasses import dataclass

STATUS_SCORE = {"pass": 1.0, "warn": 0.5, "fail": 0.0}


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    value: float | None
    detail: str

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "value": self.value,
            "detail": self.detail,
        }


def classification_check(n_done: int, n_total: int) -> Check:
    if n_total <= 0:
        return Check("classification", "warn", None, "no articles yet")
    ratio = n_done / n_total
    status = "pass" if ratio >= 0.9 else ("warn" if ratio >= 0.5 else "fail")
    return Check("classification", status, round(ratio, 4), f"{n_done}/{n_total} done")


def evidence_check(n_covered: int, n_claims: int) -> Check:
    if n_claims <= 0:
        return Check("evidence", "warn", None, "no claims yet")
    ratio = n_covered / n_claims
    status = "pass" if ratio >= 0.8 else ("warn" if ratio >= 0.5 else "fail")
    return Check("evidence", status, round(ratio, 4), f"{n_covered}/{n_claims} covered")


def forecast_check(n_scored_models: int) -> Check:
    if n_scored_models > 0:
        return Check(
            "forecast", "pass", float(n_scored_models), f"{n_scored_models} scored models"
        )
    return Check("forecast", "warn", 0.0, "no scored models yet (natural cycle)")


def freshness_check(hours_since_last: float | None) -> Check:
    if hours_since_last is None:
        return Check("freshness", "warn", None, "no market observations yet")
    if hours_since_last <= 72:
        status = "pass"
    elif hours_since_last <= 168:
        status = "warn"
    else:
        status = "fail"
    return Check(
        "freshness", status, round(hours_since_last, 1), f"{hours_since_last:.1f}h old"
    )


def memory_check(layers_present: set[str]) -> Check:
    missing = {"raw", "event", "state"} - layers_present
    if not missing:
        return Check("memory", "pass", 1.0, "raw/event/state all present")
    return Check(
        "memory", "warn", round(len(layers_present) / 3.0, 4),
        f"missing layers: {sorted(missing)}",
    )


def graph_check(n_relationships: int) -> Check:
    if n_relationships > 0:
        return Check("graph", "pass", float(n_relationships), f"{n_relationships} edges")
    return Check("graph", "warn", 0.0, "no relationships yet")


def grade_for(score: float) -> str:
    if score >= 0.9:
        return "A"
    if score >= 0.7:
        return "B"
    if score >= 0.5:
        return "C"
    return "D"


def overall(checks: list[Check]) -> tuple[float, str]:
    if not checks:
        return 0.0, "D"
    score = round(sum(STATUS_SCORE[c.status] for c in checks) / len(checks), 4)
    return score, grade_for(score)


__all__ = [
    "Check",
    "classification_check",
    "evidence_check",
    "forecast_check",
    "freshness_check",
    "grade_for",
    "graph_check",
    "memory_check",
    "overall",
]
