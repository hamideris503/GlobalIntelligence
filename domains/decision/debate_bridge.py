"""Debate -> Decision bridge — پیشنهاد تصمیم‌یار از خروجی debate (Step 5).

گیت‌های سخت (قطعی، بدون AI):
1. run نامعتبر/ناموفق → decision=insufficient_evidence.
2. disagreement بالای آستانه (DISAGREE(io)GATE=0.25, v1 مستند) → decision=no_action با توضیح.
3. scorecard ناکافی یا debate برنده نیست → برچسب experimental (نه توصیه):
   model="decision_debate_v1:experimental"؛ در غیر این صورت model="decision_debate_v1".

نگاشت جهت (v1 مستند): consensus>0.55 → up؛ <0.45 → down؛ وگرنه flat.
امتیاز: (consensus-0.5)*2 در [1,1-].
اطمینان: میانگین confidence پیام‌های دور نهایی × (1 - min(1, disagreement*2)).

هر پیشنهاد شامل: جهت، احتمال، عدم‌قطعیت، شواهد (نام agent + لینک رویدادها از
context pack)، شروط ابطال، افق، و هشدار «توصیه‌ی مالی نیست».
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.debate import DebateMessage, DebateRun
from backend.database.models.recommendation import Recommendation
from domains.debate.scorecard import ScorecardBuilder

logger = get_logger(__name__)

MODEL = "decision_debate_v1"
DISAGREE_GATE = 0.25
UP_AT = 0.55
DOWN_AT = 0.45
NOT_FINANCIAL_ADVICE_FA = "هشدار: این یک توصیه‌ی مالی نیست؛ صرفاً خروجی تصمیم‌یار است."


@dataclass
class BridgeOutcome:
    decision_id: str | None = None
    decision: str = "failed"
    experimental: bool = False
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    def as_dict(self) -> dict:
        return {
            "decision_id": self.decision_id, "decision": self.decision,
            "experimental": self.experimental, "errors": self.errors,
        }


def _parse_messages(run_id: uuid.UUID, db: Session) -> list[DebateMessage]:
    return list(db.execute(
        select(DebateMessage)
        .where(DebateMessage.run_id == run_id)
        .order_by(DebateMessage.round_no, DebateMessage.agent)
    ).scalars().all())


def _final_round(messages: list[DebateMessage]) -> list[DebateMessage]:
    rounds = [m for m in messages
              if m.agent not in ("report", "quant_anchor") and m.probability_up is not None]
    if not rounds:
        return []
    top = max(m.round_no for m in rounds)
    return [m for m in rounds if m.round_no == top]


def _response_json(m: DebateMessage) -> dict:
    try:
        d = json.loads(m.response_text or "{}")
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def build_proposal(db: Session, run_id: uuid.UUID) -> BridgeOutcome:
    """پیشنهاد تصمیم‌یار از یک debate run (افزودنی؛ بدون AI)."""
    out = BridgeOutcome()
    run = db.get(DebateRun, run_id)
    if run is None:
        out.errors.append("debate run not found")
        return out

    def _gate(decision: str, why: str, experimental: bool = False) -> BridgeOutcome:
        rec = Recommendation(
            asset=run.target, direction=None, horizon=f"{run.horizon_days or 30}d",
            decision=decision, score=0.0, confidence=0.0,
            expected_return=None, downside=None,
            probability_up=run.consensus_probability, probability_down=(
                round(1.0 - run.consensus_probability, 4)
                if run.consensus_probability is not None else None),
            base_scenario=None, bull_scenario=None, bear_scenario=None, tail_risk=None,
            evidence_for=f"debate_run={run.id}; {why}",
            evidence_against=None, main_drivers=None, main_risks=NOT_FINANCIAL_ADVICE_FA,
            invalidation=None,
            model=f"{MODEL}:experimental" if experimental else MODEL,
            data_version=run.context_hash, rank=None,
        )
        db.add(rec)
        db.commit()
        out.decision_id = str(rec.id)
        out.decision = decision
        out.experimental = experimental
        return out

    if run.status != "done" or run.consensus_probability is None:
        return _gate("insufficient_evidence",
                     f"run status={run.status}; no consensus available")

    disagreement = float(run.disagreement or 0.0)
    if disagreement > DISAGREE_GATE:
        return _gate("no_action",
                     f"disagreement {disagreement:.3f} > gate {DISAGREE_GATE} (v1)")

    card = ScorecardBuilder(db).build(target=run.target)
    experimental = not (card.sufficient and card.verdict == "debate_wins")
    gate_note = ("scorecard: " + card.verdict + f" (n={card.n_resolved})"
                 + (" -> experimental" if experimental else ""))

    consensus = float(run.consensus_probability)
    direction = "up" if consensus > UP_AT else ("down" if consensus < DOWN_AT else "flat")
    score = round(max(-1.0, min(1.0, (consensus - 0.5) * 2.0)), 4)

    messages = _parse_messages(run.id, db)
    final = _final_round(messages)
    mean_conf = (sum(m.confidence for m in final if m.confidence is not None)
                 / len(final)) if final else 0.0
    confidence = round(max(0.0, min(1.0, mean_conf * (1.0 - min(1.0, disagreement * 2.0)))), 4)

    # شواهد: نام agentها + لینک رویدادها از context pack
    try:
        pack = json.loads(run.context_pack or "{}")
    except Exception:  # noqa: BLE001
        pack = {}
    ev_by_ref = {e.get("ref_id"): e.get("event_id") for e in (pack.get("events") or [])
                 if isinstance(e, dict)}
    for_ev, against_ev, invalidations = [], [], []
    for m in final:
        d = _response_json(m)
        linked = []
        for e in (d.get("key_evidence") or [])[:6]:
            if isinstance(e, str):
                linked.append(f"{m.agent}:(unlinked):{e[:150]}")
                continue
            if not isinstance(e, dict):
                continue
            ref = e.get("ref_id", "")
            eid = ev_by_ref.get(ref)
            linked.append(f"{m.agent}:{ref}" + (f"->event:{eid[:8]}" if eid else "(unlinked)"))
        for_ev.extend(linked)
        invalidations.extend(str(x)[:200] for x in (d.get("invalidation_conditions") or [])[:3])
    critic = next((m for m in final if m.agent == "risk_critic"), None)
    if critic is not None:
        against_ev.append(f"risk_critic: {str(_response_json(critic).get('change_reason') or '')[:300]}")

    uncertainty = (f"consensus={consensus:.3f} disagreement={disagreement:.3f} "
                   f"confidence={confidence:.3f} n_agents={len(final)}; {gate_note}")
    rec = Recommendation(
        asset=run.target, direction=direction, horizon=f"{run.horizon_days or 30}d",
        decision="hold",
        score=score, confidence=confidence,
        expected_return=run.reference_price, downside=None,
        probability_up=consensus,
        probability_down=round(1.0 - consensus, 4),
        base_scenario=f"consensus P(up)={consensus:.4f}",
        bull_scenario=None, bear_scenario=None, tail_risk=None,
        evidence_for="; ".join(for_ev[:20]) or f"debate_run={run.id}",
        evidence_against="; ".join(against_ev) or None,
        main_drivers=f"debate consensus {consensus:.3f} over {len(final)} agents; {gate_note}; {uncertainty}",
        main_risks=NOT_FINANCIAL_ADVICE_FA,
        invalidation="; ".join(dict.fromkeys(invalidations))[:2000] or None,
        model=f"{MODEL}:experimental" if experimental else MODEL,
        data_version=run.context_hash, rank=None,
    )
    db.add(rec)
    db.commit()
    out.decision_id = str(rec.id)
    out.decision = "hold"
    out.experimental = experimental
    logger.info("debate proposal | run=%s decision=hold experimental=%s", run.id, experimental)
    return out
