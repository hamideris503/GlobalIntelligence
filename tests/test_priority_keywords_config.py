"""تنظیمات واژگان موتور اولویت — منبع فایل، رفتار پیش‌فرض یکسان.

هیچ شبکه/AI/DB زنده؛ فقط خواندن TOML و تابع خالص score_item.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from source_bot.config import BotSettings
from source_bot.priority_engine import (
    KEYWORD_GROUPS,
    LEVELS,
    UNRELIABLE_CONFIDENCE,
    PriorityKeywordsError,
    load_priority_keywords,
    normalize_fa,
    priority_provenance,
    score_item,
)

# واژه‌های اصلی که پیش از این در priority_engine.py هاردکد بودند (golden پیش‌فرض).
DEFAULT_KEYWORDS = {
    "urgent_fa": [
        "فوری", "اضطراری", "بحران", "هشدار", "زلزله", "جنگ", "حمله", "تحریم",
        "ورشکستگی", "فروپاشی", "تعطیلی", "انفجار", "کودتا", "آتش",
    ],
    "urgent_en": [
        "breaking", "urgent", "emergency", "crisis", "alert", "earthquake",
        "war", "attack", "sanction", "bankrupt", "collapse", "explosion", "coup",
    ],
    "high_fa": ["بانک مرکزی", "نرخ بهره", "تورم", "انتخابات", "توافق", "مذاکره", "نفت", "ارز"],
    "high_en": ["central bank", "interest rate", "inflation", "election",
                "agreement", "oil price", "exchange rate"],
    "conflict": ["contradict", "disputed", "conflict", "متناقض", "اختلاف"],
}

FILLER = "plain filler text " * 10


def _write(tmp_path, text: str) -> str:
    path = tmp_path / "priority_keywords.toml"
    path.write_text(text, encoding="utf-8")
    return str(path)


def _dump_toml(groups: dict[str, list[str]]) -> str:
    # json.dumps برای آرایه‌ی رشته‌های ساده، خروجی سازگار با TOML می‌دهد.
    return "".join(f"{name} = {json.dumps(words, ensure_ascii=False)}\n"
                   for name, words in groups.items())


def test_default_config_contains_all_existing_keywords():
    loaded = load_priority_keywords()
    assert set(loaded) == set(KEYWORD_GROUPS)
    assert loaded == DEFAULT_KEYWORDS


def test_no_hardcoded_keyword_constants_remain():
    import source_bot.priority_engine as pe

    for name in ("URGENT_FA", "URGENT_EN", "HIGH_FA", "HIGH_EN", "_CONFLICT"):
        assert not hasattr(pe, name), name


def test_loading_is_independent_of_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_priority_keywords() == DEFAULT_KEYWORDS


def test_editing_config_changes_engine_without_code_change(tmp_path):
    s = BotSettings()
    title = "orange juice market report"
    base = score_item(title=title, body=FILLER, settings=s, keywords=DEFAULT_KEYWORDS)
    assert "HIGH_IMPACT" not in base.reason_codes

    added = {k: list(v) for k, v in DEFAULT_KEYWORDS.items()}
    added["high_en"] = [*added["high_en"], "orange juice"]
    grown = load_priority_keywords(_write(tmp_path, _dump_toml(added)))
    hit = score_item(title=title, body=FILLER, settings=s, keywords=grown)
    assert "HIGH_IMPACT" in hit.reason_codes
    assert hit.score > base.score

    removed = {k: list(v) for k, v in DEFAULT_KEYWORDS.items()}
    removed["urgent_en"] = [w for w in removed["urgent_en"] if w != "coup"]
    shrunk = load_priority_keywords(_write(tmp_path, _dump_toml(removed)))
    no_hit = score_item(title="coup report", body=FILLER, settings=s, keywords=shrunk)
    assert "URGENT_KEYWORD" not in no_hit.reason_codes
    assert "URGENT_KEYWORD" in score_item(
        title="coup report", body=FILLER, settings=s, keywords=DEFAULT_KEYWORDS).reason_codes


def test_default_results_preserved():
    s = BotSettings()
    # مسیر پیش‌فرض (= فایل) باید عیناً همان نتیجه‌ی dict صریح را بدهد.
    for title in ("war report", "جنگ", "ارز دلار", "central bank meeting",
                  "reward", "جنگل شمال", "note"):
        assert score_item(title=title, body=FILLER, settings=s) == score_item(
            title=title, body=FILLER, settings=s, keywords=DEFAULT_KEYWORDS)
    assert score_item(title=None, body=None, settings=s).level == "P4"
    p0 = score_item(title="زلزله فوری و هشدار اضطراری بحران", body=("کمک فوری " * 60),
                    source_priority=1, category="alert",
                    published_at=datetime.now(UTC), has_author=True, settings=s)
    assert p0.level == "P0"


@pytest.mark.parametrize("title", ["reward", "software", "coupon",
                                   "ارزش سهام", "ارزیابی عملکرد", "جنگل شمال"])
def test_false_positive_samples_stay_low(title):
    r = score_item(title=title, body=FILLER, settings=BotSettings())
    assert "URGENT_KEYWORD" not in r.reason_codes
    assert "HIGH_IMPACT" not in r.reason_codes
    assert r.score == 20.0


@pytest.mark.parametrize("title,code", [
    ("war", "URGENT_KEYWORD"), ("coup", "URGENT_KEYWORD"),
    ("جنگ", "URGENT_KEYWORD"), ("ارز دلار", "HIGH_IMPACT"),
])
def test_important_samples_still_detected(title, code):
    assert code in score_item(title=title, body=FILLER, settings=BotSettings()).reason_codes


def test_fa_normalization_and_raw_text_preserved():
    assert normalize_fa("\u0643\u06cc \u064a") == normalize_fa("\u06a9\u06cc \u06cc")
    arabic = "\u0628\u0627\u0646\u0643 \u0645\u0631\u0643\u0632\u06cc"  # «بانك مركزی» با ك عربی
    assert normalize_fa(arabic) == "\u0628\u0627\u0646\u06a9 \u0645\u0631\u06a9\u0632\u06cc"
    assert arabic == "\u0628\u0627\u0646\u0643 \u0645\u0631\u0643\u0632\u06cc"  # متن اصلی دستنخورده
    assert "HIGH_IMPACT" in score_item(
        title=arabic, body=FILLER, settings=BotSettings()).reason_codes


def test_broken_toml_raises_clear_error(tmp_path):
    with pytest.raises(PriorityKeywordsError):
        load_priority_keywords(_write(tmp_path, "urgent_fa = [ \"x\"\n"))


def test_missing_group_raises(tmp_path):
    partial = {k: v for k, v in DEFAULT_KEYWORDS.items() if k != "conflict"}
    with pytest.raises(PriorityKeywordsError, match="conflict"):
        load_priority_keywords(_write(tmp_path, _dump_toml(partial)))


def test_wrong_type_group_raises(tmp_path):
    partial = {k: v for k, v in DEFAULT_KEYWORDS.items() if k != "conflict"}
    text = _dump_toml(partial) + 'conflict = "nope"\n'
    with pytest.raises(PriorityKeywordsError, match="conflict"):
        load_priority_keywords(_write(tmp_path, text))


def test_missing_file_raises(tmp_path):
    with pytest.raises(PriorityKeywordsError, match="not found"):
        load_priority_keywords(str(tmp_path / "does-not-exist.toml"))


def test_provenance_confidence_codes_and_levels_unchanged():
    r = score_item(title="war report", body=FILLER, settings=BotSettings())
    assert r.level in LEVELS
    assert "URGENT_KEYWORD" in r.reason_codes
    assert 0.05 <= r.confidence <= 0.95
    prov = priority_provenance(rules_confidence=r.confidence, ai=None)
    assert set(prov) == {
        "priority_decision_source", "priority_score_source", "priority_confidence",
        "rules_priority_confidence", "ai_priority_confidence",
        "ai_priority_reason", "ai_priority_reason_codes",
    }
    assert prov["priority_score_source"] == "rules"
    assert prov["priority_decision_source"] in ("rules", "pending")


def test_existing_public_contract_still_available():
    assert LEVELS == ("P0", "P1", "P2", "P3", "P4")
    assert UNRELIABLE_CONFIDENCE == 0.3
