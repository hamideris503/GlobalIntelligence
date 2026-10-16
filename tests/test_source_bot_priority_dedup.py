"""Dedup + priority + security tests (pure, بدون شبکه)."""
from __future__ import annotations

from datetime import UTC, datetime

from source_bot.ai_priority_fallback import validate_ai_priority
from source_bot.config import BotSettings
from source_bot.deduplicator import canonical_url, exact_key, near_duplicate
from source_bot.priority_engine import normalize_fa, score_item
from source_bot.security import redact_headers, validate_url


def test_exact_key_prefers_external_id():
    assert exact_key("X", "http://a", "h") == "ext:X"
    assert exact_key(None, "http://a/", None).startswith("url:http")


def test_canonical_url_normalizes():
    assert canonical_url("https://EX.com/path/") == "https://ex.com/path"
    assert canonical_url("ftp://ex.com") is None


def test_near_duplicate_identical_vs_different():
    a = "the central bank raised interest rates today amid inflation fears " * 3
    assert near_duplicate(a, a).is_duplicate is True
    b = "football match results and weather forecast for the weekend games"
    assert near_duplicate(a, b).is_duplicate is False


def test_series_periods_are_not_duplicates():
    k1 = exact_key(None, None, "ind:GDP:2023")
    k2 = exact_key(None, None, "ind:GDP:2024")
    assert k1 != k2


def test_priority_all_five_levels():

    s = BotSettings()
    now = datetime.now(UTC)
    p0 = score_item(title="زلزله فوری و هشدار اضطراری بحران", body=("کمک فوری " * 60),
                    source_priority=1, category="alert", published_at=now, has_author=True, settings=s)
    assert p0.level == "P0"
    p1 = score_item(title="central bank interest rate breaking decision", body=("analysis text " * 60),
                    published_at=now, has_author=True, settings=s)
    assert p1.level in ("P0", "P1")
    assert score_item(title="market report", body="quarterly overview data " * 20, settings=s).level in ("P1", "P2", "P3")
    assert score_item(title="note", body="short", settings=s).level in ("P3", "P4")
    assert score_item(title=None, body=None, settings=s).level == "P4"


def test_priority_no_ai_for_clear_rules():

    r = score_item(title="central bank raises interest rates sharply",
                   body=("detailed market analysis with complete data " * 60),
                   published_at=datetime.now(UTC), has_author=True)
    assert r.needs_ai is False


def test_priority_needs_ai_near_border_or_conflict():
    r = score_item(title="breaking but disputed contradict claims", body="text " * 50)
    assert r.needs_ai is True or "CONFLICT_SIGNAL" in r.reason_codes


def test_fa_normalization():
    assert normalize_fa("كی ي") == normalize_fa("کی ی")


def test_keyword_substring_is_not_a_hit():
    """زیررشته به‌تنهایی امتیاز نمی‌دهد (reward/software/coupon/ارزش/ارزیابی/جنگل)."""
    s = BotSettings()
    filler = "plain filler text " * 10
    for title in ("reward", "software", "coupon", "team award news",
                  "ارزش سهام", "ارزیابی عملکرد", "جنگل شمال"):
        r = score_item(title=title, body=filler, settings=s)
        assert "URGENT_KEYWORD" not in r.reason_codes, title
        assert "HIGH_IMPACT" not in r.reason_codes, title
        assert r.score == 20.0, title


def test_keyword_standalone_match_kept():
    """واژه مستقل (با حروف مختلف و نشانه‌گذاری) همچنان تشخیص داده می‌شود."""
    s = BotSettings()
    filler = "plain filler text " * 10
    for title, code in (("war", "URGENT_KEYWORD"), ("coup", "URGENT_KEYWORD"),
                        ("WAR", "URGENT_KEYWORD"), ("War", "URGENT_KEYWORD"),
                        ("(war)", "URGENT_KEYWORD"), ("war,", "URGENT_KEYWORD"),
                        ("coup.", "URGENT_KEYWORD"), ("market war report", "URGENT_KEYWORD"),
                        ("جنگ", "URGENT_KEYWORD"), ("ارز دلار", "HIGH_IMPACT"),
                        ("نرخ ارز و طلا", "HIGH_IMPACT")):
        r = score_item(title=title, body=filler, settings=s)
        assert code in r.reason_codes, title
    # چندواژه‌ای‌ها رفتار زیررشته‌ای قبلی را حفظ می‌کنند
    r = score_item(title="central bank meeting", body=filler, settings=s)
    assert "HIGH_IMPACT" in r.reason_codes


def test_ai_schema_rejects_bad():
    assert validate_ai_priority({}) is None
    assert validate_ai_priority({"priority": "P9", "confidence": 0.9, "reason": "r", "reason_codes": []}) is None
    assert validate_ai_priority({"priority": "P1", "confidence": 2.0, "reason": "r", "reason_codes": []}) is None
    good = validate_ai_priority({"priority": "P1", "confidence": 0.91, "reason": "ok", "reason_codes": ["HIGH_IMPACT"]})
    assert good and good["priority"] == "P1"


def test_security_blocks():
    assert validate_url("ftp://x.com").ok is False
    assert validate_url("http://user:pw@example.com/").ok is False
    assert validate_url("http://127.0.0.1/").ok is False
    assert validate_url("http://10.0.0.5/x").ok is False
    assert validate_url("http://[::1]/").ok is False
    assert validate_url("http://169.254.169.254/").ok is False
    assert validate_url("https://example.com/rss").ok is True


def test_no_credential_leak_in_logs():
    h = redact_headers({"Authorization": "Bearer SECRET", "Accept": "x"})
    assert h["Authorization"] == "***" and "SECRET" not in str(h.values())
