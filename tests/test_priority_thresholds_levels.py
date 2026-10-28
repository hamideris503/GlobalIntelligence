"""آستانه‌های اولویت (محدوده/ترتیب) و اعتبارسنجی سطح P0..P4 در مرزها.

بدون شبکه/AI/DB واقعی؛ فقط SQLite موقت و توابع خالص.
"""
from __future__ import annotations

from typing import get_args

import pytest
from pydantic import ValidationError

from backend.api.schemas.ingestion import DocumentRead, PriorityLevel
from backend.database import models as _models
from backend.database.models.source import Source
from domains.news.fetchers import RawItem
from source_bot.config import BotConfigError, BotSettings
from source_bot.output import deliver
from source_bot.priority_engine import LEVELS, _level_for, is_valid_level, score_item
from tests.conftest import TestingSession

# --- آستانه‌ها: پیش‌فرض معتبر ---

def test_default_thresholds_valid_and_unchanged():
    s = BotSettings()
    assert (s.th_p0, s.th_p1, s.th_p2, s.th_p3) == (90.0, 75.0, 50.0, 25.0)


# --- آستانه‌ها: خارج از محدوده / غیرعددی ---

@pytest.mark.parametrize("name,value", [
    ("SOURCE_BOT_TH_P0", "150"),
    ("SOURCE_BOT_TH_P1", "-1"),
    ("SOURCE_BOT_TH_P2", "100.5"),
    ("SOURCE_BOT_TH_P3", "nan"),
    ("SOURCE_BOT_TH_P0", "inf"),
])
def test_threshold_out_of_range_rejected(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(BotConfigError):
        BotSettings()


def test_threshold_non_numeric_rejected(monkeypatch):
    monkeypatch.setenv("SOURCE_BOT_TH_P2", "abc")
    with pytest.raises(BotConfigError):
        BotSettings()


# --- آستانه‌ها: ترتیب ناسازگار ---

@pytest.mark.parametrize("env", [
    {"SOURCE_BOT_TH_P0": "50", "SOURCE_BOT_TH_P1": "75"},          # وارونگی
    {"SOURCE_BOT_TH_P0": "90", "SOURCE_BOT_TH_P1": "90"},          # تساوی
    {"SOURCE_BOT_TH_P2": "10", "SOURCE_BOT_TH_P3": "20"},          # وارونگی پایین
    {"SOURCE_BOT_TH_P3": "90"},                                     # پ3 بالاتر از پیش‌فرض p0
])
def test_threshold_order_rejected(monkeypatch, env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(BotConfigError):
        BotSettings()


# --- مرزها: مقدار مساوی دقیقاً یک سطح ---

def test_threshold_equality_maps_to_expected_level():
    s = BotSettings()
    assert _level_for(100.0, s) == "P0"
    assert _level_for(90.0, s) == "P0"   # == th_p0
    assert _level_for(89.9, s) == "P1"
    assert _level_for(75.0, s) == "P1"   # == th_p1
    assert _level_for(74.9, s) == "P2"
    assert _level_for(50.0, s) == "P2"   # == th_p2
    assert _level_for(49.9, s) == "P3"
    assert _level_for(25.0, s) == "P3"   # == th_p3
    assert _level_for(24.9, s) == "P4"
    assert _level_for(0.0, s) == "P4"


# --- تنظیمات سفارشی معتبر ---

def test_custom_valid_thresholds_supported(monkeypatch):
    monkeypatch.setenv("SOURCE_BOT_TH_P0", "80")
    monkeypatch.setenv("SOURCE_BOT_TH_P1", "60")
    monkeypatch.setenv("SOURCE_BOT_TH_P2", "40")
    monkeypatch.setenv("SOURCE_BOT_TH_P3", "20")
    s = BotSettings()
    assert (s.th_p0, s.th_p1, s.th_p2, s.th_p3) == (80.0, 60.0, 40.0, 20.0)
    assert _level_for(80.0, s) == "P0"
    assert _level_for(60.0, s) == "P1"
    assert _level_for(40.0, s) == "P2"
    assert _level_for(20.0, s) == "P3"
    assert _level_for(19.9, s) == "P4"
    assert score_item(title="war", body=None, settings=s).level in LEVELS


# --- اعتبارسنجی سطح ---

@pytest.mark.parametrize("value", list(LEVELS))
def test_is_valid_level_accepts_all_levels(value):
    assert is_valid_level(value)


@pytest.mark.parametrize("value", ["P5", "UNKNOWN", "", "p0", " P0", "P0 ", None, 0, ["P0"]])
def test_is_valid_level_rejects_others(value):
    assert not is_valid_level(value)


def test_priority_level_literal_matches_engine_levels():
    assert set(get_args(PriorityLevel)) == set(LEVELS)


# --- مرز ذخیره‌سازی: deliver ---

@pytest.mark.parametrize("bad", ["P5", "UNKNOWN", "", None, "p0"])
def test_deliver_rejects_invalid_level(bad):
    session = TestingSession()
    try:
        s = Source(name="lv", domain="lv.local", type="rss", active=True)
        session.add(s)
        session.commit()
        with pytest.raises(ValueError):
            deliver(session, s, RawItem(title="x", url="https://lv.local/1", raw_text="y"),
                    priority=bad, score=10.0, reason="rules score=10.0",
                    priority_source="rules", priority_status="RULES_ONLY",
                    duplicate_status="new")
        assert session.query(_models.Document).count() == 0
    finally:
        session.close()


def test_deliver_accepts_all_valid_levels():
    session = TestingSession()
    try:
        s = Source(name="oklv", domain="oklv.local", type="rss", active=True)
        session.add(s)
        session.commit()
        for i, level in enumerate(LEVELS):
            assert deliver(
                session, s, RawItem(title=f"t{i}", url=f"https://oklv.local/{i}", raw_text="body"),
                priority=level, score=10.0, reason="rules score=10.0",
                priority_source="rules", priority_status="RULES_ONLY",
                duplicate_status="new") is True
        stored = {d.ingestion_priority for d in session.query(_models.Document).all()}
        assert stored == set(LEVELS)
    finally:
        session.close()


# --- مرز API: خروجی ---

@pytest.mark.parametrize("value", list(LEVELS))
def test_document_read_accepts_valid_priority(value):
    row = DocumentRead(id="1", source_id=None, url=None, title=None, language=None, author=None,
                       published_at=None, retrieved_at=None, content_hash=None,
                       ingestion_priority=value)
    assert row.ingestion_priority == value


def test_document_read_allows_null_priority():
    row = DocumentRead(id="1", source_id=None, url=None, title=None, language=None, author=None,
                       published_at=None, retrieved_at=None, content_hash=None)
    assert row.ingestion_priority is None


@pytest.mark.parametrize("value", ["P5", "UNKNOWN", "", "p0", " P0"])
def test_document_read_rejects_invalid_priority(value):
    with pytest.raises(ValidationError):
        DocumentRead(id="1", source_id=None, url=None, title=None, language=None, author=None,
                     published_at=None, retrieved_at=None, content_hash=None,
                     ingestion_priority=value)


# --- AI fallback و provenance دست‌نخورده ---

def test_ai_level_validation_and_provenance_unchanged():
    from source_bot.ai_priority_fallback import validate_ai_priority
    from source_bot.priority_engine import priority_provenance

    base = {"confidence": 0.9, "reason": "why", "reason_codes": []}
    assert validate_ai_priority({**base, "priority": "P5"}) is None
    assert validate_ai_priority({**base, "priority": "P1"})["priority"] == "P1"

    prov = priority_provenance(rules_confidence=0.9, ai=None)
    assert prov["priority_decision_source"] == "rules"
    assert prov["priority_score_source"] == "rules"
