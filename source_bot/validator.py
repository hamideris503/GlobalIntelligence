"""Validator — بررسی هر SourcePlan پیش از fetch (امنیت + قرارداد)."""
from __future__ import annotations

from dataclasses import dataclass

from source_bot.registry import SourcePlan
from source_bot.security import validate_url


@dataclass
class PlanCheck:
    ok: bool
    reason: str = ""


def validate_source_plan(plan: SourcePlan) -> PlanCheck:
    if plan.adapter == "specialized":
        return PlanCheck(True, "specialized owner kept")
    if plan.adapter == "skip" or not plan.url:
        return PlanCheck(False, f"skip: {plan.reason}")
    chk = validate_url(plan.url)
    if not chk.ok:
        return PlanCheck(False, chk.reason)
    return PlanCheck(True, "")
