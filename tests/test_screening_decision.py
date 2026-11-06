"""Tri-state screening decision tests (F04.1)."""
from __future__ import annotations

from backend.ai.local_screening.decision import (
    ScreeningVerdict,
    decide,
)


def test_both_high_agree_relevant():
    r = decide(kev_probability=0.9, laya_probability=0.85)
    assert r.verdict == ScreeningVerdict.RELEVANT
    assert r.reason == "decided"


def test_both_high_agree_irrelevant():
    r = decide(kev_probability=0.1, laya_probability=0.15)
    assert r.verdict == ScreeningVerdict.IRRELEVANT


def test_disagreement_uncertain():
    r = decide(kev_probability=0.9, laya_probability=0.1)
    assert r.verdict == ScreeningVerdict.UNCERTAIN
    assert r.reason == "model_disagreement"


def test_low_confidence_uncertain():
    r = decide(kev_probability=0.55, laya_probability=0.52)
    assert r.verdict == ScreeningVerdict.UNCERTAIN
    assert r.reason == "low_confidence"


def test_runtime_error_uncertain():
    r = decide(kev_probability=0.9, laya_probability=0.9, runtime_error=True)
    assert r.verdict == ScreeningVerdict.UNCERTAIN
    assert r.reason == "runtime_error_or_timeout"


def test_timeout_uncertain():
    r = decide(kev_probability=0.9, laya_probability=0.9, timeout=True)
    assert r.verdict == ScreeningVerdict.UNCERTAIN


def test_kev_unavailable_uncertain():
    r = decide(kev_probability=0.9, laya_probability=0.9, kev_ok=False)
    assert r.verdict == ScreeningVerdict.UNCERTAIN


def test_laya_unavailable_uncertain():
    r = decide(kev_probability=0.9, laya_probability=0.9, laya_ok=False)
    assert r.verdict == ScreeningVerdict.UNCERTAIN


def test_no_output_uncertain():
    r = decide(kev_probability=None, laya_probability=None)
    assert r.verdict == ScreeningVerdict.UNCERTAIN
    assert r.reason == "no_model_output"


def test_rules_model_conflict_uncertain():
    r = decide(kev_probability=0.9, laya_probability=0.85, rules_relevant=False)
    assert r.verdict == ScreeningVerdict.UNCERTAIN
    assert r.reason == "rules_model_conflict"


def test_rules_agree_relevant():
    r = decide(kev_probability=0.9, laya_probability=0.85, rules_relevant=True)
    assert r.verdict == ScreeningVerdict.RELEVANT


def test_single_model_kev_only():
    r = decide(kev_probability=0.9)
    assert r.verdict == ScreeningVerdict.RELEVANT


def test_single_model_laya_only_low():
    r = decide(laya_probability=0.55)
    assert r.verdict == ScreeningVerdict.UNCERTAIN


def test_invalid_prob_ignored():
    r = decide(kev_probability=1.5, laya_probability=0.9)
    # 1.5 invalid -> treated as None; only laya remains
    assert r.kev_probability is None
    assert r.laya_probability == 0.9


def test_bool_prob_rejected():
    r = decide(kev_probability=True, laya_probability=0.9)
    assert r.kev_probability is None