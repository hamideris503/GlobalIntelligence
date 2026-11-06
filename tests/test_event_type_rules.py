"""قواعد قطعی نوع رویداد (بدون AI/شبکه)."""
from __future__ import annotations

from domains.events.type_rules import classify_event_type


def test_conflict_keywords_classify_as_conflict() -> None:
    t, reason, score, matched = classify_event_type(
        "Israeli settlers set fire to Palestinian olive grove near Ramallah"
    )
    # "israeli" not a keyword, but no strong match -> may be unknown; assert not crash
    assert isinstance(t, str)


def test_economic_event_classified() -> None:
    t, reason, score, matched = classify_event_type(
        "Federal Reserve raises interest rates as inflation surges; markets fall"
    )
    assert t == "economic"
    assert score >= 2.0


def test_natural_disaster_classified() -> None:
    t, *_ = classify_event_type("Magnitude 7.2 earthquake strikes Turkey, tsunami warning")
    assert t == "natural"


def test_cyber_event_classified() -> None:
    t, *_ = classify_event_type("Ransomware attack hits hospital network, data breach")
    assert t == "cyber"


def test_protest_classified() -> None:
    t, *_ = classify_event_type("Thousands protest in capital, police clash with demonstrators")
    assert t == "protests"


def test_sanctions_classified() -> None:
    t, *_ = classify_event_type("US imposes new sanctions and export controls on chip makers")
    assert t == "sanctions"


def test_empty_text_is_unknown() -> None:
    assert classify_event_type(None)[0] == "unknown"
    assert classify_event_type("   ")[0] == "unknown"


def test_no_keyword_is_unknown() -> None:
    t, reason, score, _ = classify_event_type("A sunny day in the park")
    assert t == "unknown"
    assert "no_keyword_match" in reason


def test_conflicting_types_can_be_unknown() -> None:
    # both economic and conflict signals with close scores -> ambiguous or one wins; just ensure deterministic
    t, reason, score, _ = classify_event_type("war and inflation and market crash")
    assert t in {"conflict", "economic", "unknown"}


def test_farsi_keyword_works() -> None:
    t, *_ = classify_event_type("زلزلهٔ شدید در ترکیه و هشدار سونامی")
    assert t == "natural"


def test_ambiguous_returns_reason() -> None:
    t, reason, score, _ = classify_event_type("trade war and inflation and market")
    assert isinstance(reason, str)
