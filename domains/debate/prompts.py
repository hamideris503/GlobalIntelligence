"""Debate prompts — نسخه‌دار (Step 3)."""
from __future__ import annotations

PROMPT_VERSION = "debate_v1"


def round1_prompt(*, agent: str, role: str, target: str, target_date: str,
                  context_json: str) -> str:
    return (
        f"{role}\n\n"
        f"QUESTION: Will the price of {target} be HIGHER on {target_date} "
        f"than the reference price below?\n"
        f"Answer with probability_up = P(price higher).\n\n"
        f"CONTEXT PACK (fixed; cite ONLY ref_ids from it):\n{context_json}\n\n"
        "RULES: output strict JSON per schema. direction must match probability_up "
        "(>0.5 up, <0.5 down, ==0.5 flat). Never invent ref_ids. "
        "If evidence is thin, lower confidence and say so in uncertainties."
    )


def round2_prompt(*, agent: str, role: str, target: str, target_date: str,
                  context_json: str, others_json: str, own_json: str) -> str:
    return (
        f"{role}\n\n"
        f"QUESTION: Will the price of {target} be HIGHER on {target_date}?\n"
        f"OTHER AGENTS' ROUND-1 VIEWS:\n{others_json}\n\n"
        f"YOUR ROUND-1 VIEW:\n{own_json}\n\n"
        f"CONTEXT PACK:\n{context_json}\n\n"
        "RULES: say what you accept/reject from others and why. Update probability_up "
        "if convinced; if unchanged, explain why in change_reason with changed_mind=false. "
        "Output strict JSON per schema. Never invent ref_ids."
    )


def repair_prompt(*, context_json: str) -> str:
    return (
        "You output ONLY a JSON object per the schema. No prose, no markdown fences. "
        f"Context:\n{context_json}"
    )


def report_prompt(*, target: str, consensus: float, disagreement: float,
                  agents_json: str) -> str:
    return (
        "You are the debate rapporteur. Write a short Persian-or-English narrative "
        "(match the agents' language) explaining the consensus, the disagreement, "
        "key evidence both sides, and invalidation conditions. "
        "You set NO numbers; numbers are computed deterministically elsewhere.\n\n"
        f"TARGET: {target}\nCONSENSUS P(up)={consensus:.3f} DISAGREEMENT={disagreement:.3f}\n"
        f"AGENT VIEWS:\n{agents_json}"
    )
