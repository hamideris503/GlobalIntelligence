"""Debate agents — نقش‌ها و schema خروجی ساختاریافته (Step 3).

quant_anchor بدون LLM است (فقط baselineهای آماری).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# agentهای LLM (به ترتیب اجرا) + نقش متنی هرکدام
AGENTS: tuple[str, ...] = ("bull", "bear", "macro", "geopolitical", "risk_critic")
QUANT_AGENT = "quant_anchor"
REPORT_AGENT = "report"

AGENT_ROLES: dict[str, str] = {
    "bull": "You argue the BULL case: the strongest honest reasons the price will be UP.",
    "bear": "You argue the BEAR case: the strongest honest reasons the price will be DOWN.",
    "macro": "You are the MACRO analyst: monetary policy, inflation, dollar, rates.",
    "geopolitical": "You are the GEOPOLITICAL analyst: supply shocks, conflicts, sanctions, OPEC+.",
    "risk_critic": "You are the RISK CRITIC: attack weak reasoning, weak evidence, repeated sources.",
    "report": "You write the final explanatory narrative. You set NO numbers.",
}

AGENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "direction": {"type": "string", "enum": ["up", "down", "flat"]},
        "probability_up": {"type": "number", "minimum": 0.02, "maximum": 0.98},
        "horizon_days": {"type": "integer", "minimum": 1},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "key_evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ref_id": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["ref_id", "why"],
            },
        },
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "invalidation_conditions": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
        "changed_mind": {"type": "boolean"},
        "change_reason": {"type": "string"},
    },
    "required": [
        "direction", "probability_up", "horizon_days", "confidence",
        "key_evidence", "assumptions", "invalidation_conditions", "uncertainties",
    ],
}

PROB_MIN, PROB_MAX = 0.02, 0.98


def normalize_output(data: dict) -> dict:
    """نرمال‌سازی بردبار پیش از اعتبارسنجی (مستند).

    برخی مدل‌ها key_evidence را آرایه‌ای از رشته برمی‌گردانند نه آبجکت؛
    رشته‌ها به {ref_id:"", why:text} تبدیل می‌شوند تا اعتبارسنجی بگذرد،
    سپس چون ref_id تهی در بسته نیست، رد و در quality_score لحاظ می‌شوند.
    """
    ev = data.get("key_evidence")
    if isinstance(ev, list):
        norm = []
        for item in ev:
            if isinstance(item, str):
                norm.append({"ref_id": "", "why": item[:300]})
            elif isinstance(item, dict):
                norm.append(item)
        data["key_evidence"] = norm
    return data


def clip_probability(p: float) -> float:
    """Clip قطعی احتمال به بازه‌ی مجاز."""
    return max(PROB_MIN, min(PROB_MAX, float(p)))


@dataclass
class AgentResult:
    agent: str
    direction: str
    probability_up: float
    horizon_days: int
    confidence: float
    key_evidence: list[dict] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    invalidation_conditions: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    changed_mind: bool = False
    change_reason: str = ""
    # ضد توهم: ارجاع‌های ردشده + نمره‌ی کیفیت
    rejected_refs: list[str] = field(default_factory=list)
    quality_score: float = 1.0

    @classmethod
    def from_dict(cls, agent: str, data: dict, valid_refs: set[str]) -> AgentResult:
        for key in ("direction", "probability_up", "horizon_days", "confidence"):
            if key not in data:
                raise ValueError(f"agent {agent}: missing key {key!r}")
        if data["direction"] not in ("up", "down", "flat"):
            raise ValueError(f"agent {agent}: bad direction {data['direction']!r}")
        ev = data.get("key_evidence") or []
        if not isinstance(ev, list):
            raise ValueError(f"agent {agent}: key_evidence must be a list")
        kept, rejected = [], []
        for item in ev:
            ref = (item or {}).get("ref_id", "")
            if ref in valid_refs:
                kept.append({"ref_id": ref, "why": str((item or {}).get("why", ""))[:300]})
            else:
                rejected.append(str(ref))
        quality = 1.0
        if rejected:
            # هر ارجاع جعلی ۰.۲ کسر (کف ۰.۲) — ذخیره می‌شود
            quality = max(0.2, 1.0 - 0.2 * len(rejected))
        return cls(
            agent=agent,
            direction=data["direction"],
            probability_up=clip_probability(float(data["probability_up"])),
            horizon_days=int(data["horizon_days"]),
            confidence=max(0.0, min(1.0, float(data["confidence"]))),
            key_evidence=kept,
            assumptions=[str(x)[:300] for x in (data.get("assumptions") or [])][:10],
            invalidation_conditions=[
                str(x)[:300] for x in (data.get("invalidation_conditions") or [])
            ][:10],
            uncertainties=[str(x)[:300] for x in (data.get("uncertainties") or [])][:10],
            changed_mind=bool(data.get("changed_mind", False)),
            change_reason=str(data.get("change_reason") or "")[:500],
            rejected_refs=rejected,
            quality_score=quality,
        )


def validate_agent_dict(agent: str, data: Any) -> dict:
    """اعتبارسنجی حداقلی ساختار (jsonschema کامل در engine با fallback)."""
    if not isinstance(data, dict):
        raise ValueError(f"agent {agent}: output is not a JSON object")
    return data
