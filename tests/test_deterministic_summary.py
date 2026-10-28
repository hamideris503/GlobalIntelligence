"""خلاصه‌سازی قطعی محلی خبرها (بدون AI/شبکه) — helper و مسیرهای ingest.

همه‌ی تست‌ها روی SQLite ایزوله و حافظه‌ی محلی اجرا می‌شوند؛ هیچ provider صدا
زده نمی‌شود و هیچ متن خامی بازنویسی نمی‌شود.
"""
from __future__ import annotations

import pytest

from backend.database import models as _models
from backend.database.models.source import Source
from domains.news.fetchers import RawItem
from domains.news.ingestion import NewsIngestionPipeline
from domains.news.normalizer import (
    SUMMARY_MAX_CHARS,
    clean_text,
    content_hash,
    deterministic_summary,
)
from source_bot.priority_engine import LEVELS
from tests.conftest import TestingSession

# --- helper: رفتار قطعی ---

def test_short_text_returned_unchanged():
    text = "A short news line without an unnecessary rewrite."
    assert deterministic_summary(text) == text


@pytest.mark.parametrize("text", [None, "", "   ", "...", "!!! ???", "  .  "])
def test_empty_or_contentless_returns_none(text):
    assert deterministic_summary(text) is None


def test_long_text_truncated_at_sentence_boundary_and_within_limit():
    sentence = "Sentence number one is fine. "
    out = deterministic_summary(sentence * 300)
    assert out is not None
    assert len(out) <= SUMMARY_MAX_CHARS
    assert out.endswith(".")
    assert (sentence * 300).startswith(out)


def test_single_long_sentence_cut_at_word_boundary():
    word = "abcdefghij "
    text = word * 400  # بدون نشانه‌ی پایان جمله
    out = deterministic_summary(text, limit=50)
    assert out is not None and len(out) <= 50
    assert text.startswith(out)
    assert not out.endswith(" ")


def test_sentence_boundary_selection_is_predictable():
    text = "One sentence here. Two sentence here. Three sentence here."
    assert deterministic_summary(text, limit=25) == "One sentence here."


def test_english_bang_and_question_are_boundaries():
    first = "Breaking news!"
    text = f"{first} Something else? More text follows here."
    assert deterministic_summary(text, limit=20) == first


def test_persian_period_question_semicolon_and_urdu_stop():
    assert deterministic_summary("آیا توافق امضا شد؟ پاسخ روشن نیست. ادامه.", limit=25) == (
        "آیا توافق امضا شد؟"
    )
    assert deterministic_summary("قیمت ارز افزایش یافت. بازار واکنش نشان داد؛ ادامه.", limit=25) == (
        "قیمت ارز افزایش یافت."
    )
    assert deterministic_summary("نرخ تغییر کرد۔ سپس آرام شد. ادامه.", limit=25) == (
        "نرخ تغییر کرد۔"
    )


def test_decimal_dates_prices_and_urls_do_not_split():
    first = "Rates hit 3.14 percent at https://ex.com/a.b today."
    text = f"{first} Next sentence here."
    assert deterministic_summary(text, limit=60) == first


def test_numbers_prices_and_dates_preserved_through_truncation():
    text = "Gold rose to 1,234.56 dollars on 2024.05.01. " + ("Filler sentence here. " * 400)
    out = deterministic_summary(text)
    assert "1,234.56" in out
    assert "2024.05.01" in out
    assert len(out) <= SUMMARY_MAX_CHARS


# --- مسیر عادی ingest ---

def _source(session, name: str) -> Source:
    s = Source(name=name, domain=f"{name}.local", type="rss", active=True)
    session.add(s)
    session.commit()
    return s


def test_plain_ingest_sets_deterministic_summary():
    session = TestingSession()
    try:
        s = _source(session, "sum")
        body = "The central bank raised interest rates today. " * 200
        item = RawItem(title="T", url="https://sum.local/1", raw_text=body)
        assert NewsIngestionPipeline(session).store_item(s, item) is True

        article = session.query(_models.Article).one()
        assert article.summary == deterministic_summary(clean_text(body))
        assert article.summary and len(article.summary) <= SUMMARY_MAX_CHARS
    finally:
        session.close()


def test_source_bot_path_yields_consistent_summary():
    from source_bot.output import deliver

    session = TestingSession()
    try:
        s = _source(session, "bot")
        body = "First sentence here. Second sentence follows. " * 100
        item = RawItem(title="B", url="https://bot.local/1", raw_text=body)
        assert deliver(session, s, item, priority="P1", score=80.0,
                       reason="rules score=80.0", priority_source="rules",
                       priority_status="RULES_ONLY", duplicate_status="new") is True

        article = session.query(_models.Article).one()
        assert article.summary == deterministic_summary(clean_text(body))
    finally:
        session.close()


def test_duplicate_store_does_not_rewrite_existing_summary():
    session = TestingSession()
    try:
        s = _source(session, "dup")
        body = "Alpha sentence one. Beta sentence two. " * 60
        item = RawItem(title="D", url="https://dup.local/1", raw_text=body)
        pipeline = NewsIngestionPipeline(session)
        assert pipeline.store_item(s, item) is True

        article = session.query(_models.Article).one()
        article.summary = "manual summary"
        session.commit()

        assert pipeline.store_item(s, item) is False  # duplicate
        session.expire_all()
        assert session.query(_models.Article).count() == 1
        assert session.query(_models.Article).one().summary == "manual summary"
    finally:
        session.close()


def test_raw_text_payload_title_and_priority_preserved():
    session = TestingSession()
    try:
        s = _source(session, "prov")
        payload = '{"k": 1}'
        raw_html = "<p>Raw <b>body</b> sentence one. Sentence two.</p>"
        item = RawItem(title="Prov Title", url="https://prov.local/1",
                       raw_text=raw_html, raw_payload=payload)
        assert NewsIngestionPipeline(session).store_item(s, item) is True

        doc = session.query(_models.Document).one()
        assert doc.raw_text == "Raw body sentence one. Sentence two."
        assert doc.raw_payload == payload
        assert doc.title == "Prov Title"
        assert doc.content_hash == content_hash("Prov Title", doc.raw_text)
        assert doc.ingestion_priority in LEVELS

        article = session.query(_models.Article).one()
        assert article.title == "Prov Title"
        assert article.summary == deterministic_summary(doc.raw_text)
    finally:
        session.close()


def test_summary_uses_no_ai_gateway(monkeypatch):
    from backend.ai.gateway.gateway import AIGateway

    def _boom(self, *args, **kwargs):
        raise AssertionError("AI gateway must not be constructed for deterministic summary")

    monkeypatch.setattr(AIGateway, "__init__", _boom)

    session = TestingSession()
    try:
        s = _source(session, "noai")
        body = "Sentence one is here. Sentence two is here. " * 50
        assert NewsIngestionPipeline(session).store_item(
            s, RawItem(title="N", url="https://noai.local/1", raw_text=body)) is True
        assert session.query(_models.Article).one().summary
    finally:
        session.close()
