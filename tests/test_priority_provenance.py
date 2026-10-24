"""قرارداد provenance اولویت: سطح، امتیاز قواعد، confidence و منشأ تصمیم.

هر دو مسیر (ingestion عادی و Source Bot) باید همان کلیدهای metadata را بدهند و
هیچ مقدار جعلی ثبت نکنند. همه‌ی تست‌ها روی SQLite ایزوله با AI stub اجرا می‌شوند؛
هیچ provider/شبکه‌ی زنده‌ای صدا زده نمی‌شود.
"""
from __future__ import annotations

import asyncio
import json

from backend.ai.schemas.types import AIResponse
from backend.database.models.document import Document, provenance_of
from backend.database.models.source import Source
from domains.news.classifier import PRIORITY_BANDS
from domains.news.fetchers import RawItem
from domains.news.ingestion import UNRELIABLE_CONFIDENCE, NewsIngestionPipeline
from domains.news.normalizer import content_hash, identity_hash, payload_hash
from source_bot import runner as runner_module
from source_bot.config import BotSettings
from source_bot.metrics import BotMetrics
from source_bot.priority_engine import priority_provenance, score_item
from tests.conftest import TestingSession

PROVENANCE_KEYS = {
    "priority_decision_source", "priority_score_source", "priority_confidence",
    "rules_priority_confidence", "ai_priority_confidence",
    "ai_priority_reason", "ai_priority_reason_codes",
}

# آیتمی که موتور قواعد برایش AI می‌خواهد (نزدیک مرز + متعارض) و confidence قواعدش
# پایین است — تا ورود به شاخهٔ AI در runner قطعی باشد.
_NEEDS_AI = {"title": "breaking but disputed contradict claims", "raw_text": "text " * 50}
# آیتم «قواعد قابل‌اعتماد» (confidence ≥ 0.3) — برای تفکیک fallback از pending.
_RULES_CONFIDENT = {"title": "market report", "raw_text": "quarterly overview data " * 20}


def _src(session: TestingSession, name: str) -> Source:
    s = Source(name=name, collection_method="rss", type="rss",
               feed_url=f"https://{name}.test/rss")
    session.add(s)
    session.commit()
    return s


def _meta(doc: Document) -> dict:
    return json.loads(doc.doc_metadata or "{}")


def _run_bot(monkeypatch, session: TestingSession, src: Source, item: RawItem,
             *, ai_enabled: bool, gw=None) -> BotMetrics:
    async def fake_fetch(plan, settings):
        return ([item], "", {})

    monkeypatch.setattr(runner_module, "_fetch_plan", fake_fetch)
    if gw is not None:
        monkeypatch.setattr("backend.ai.gateway.get_gateway", lambda: gw)
    settings = BotSettings()
    settings.max_retries = 0
    settings.ai_enabled = ai_enabled
    metrics = BotMetrics()
    asyncio.run(runner_module.run_source(session, src, metrics, settings))
    return metrics


# --- ۱) مسیر عادی ingestion: تصمیم قواعد ---
def test_plain_ingest_records_rules_provenance() -> None:
    session = TestingSession()
    try:
        s = _src(session, "prov-plain")
        item = RawItem(title="central bank raises interest rates sharply",
                       url="https://p.test/1",
                       raw_text="detailed market analysis with complete data " * 20)
        assert NewsIngestionPipeline(session).store_item(s, item) is True

        doc = session.query(Document).one()
        expected = score_item(title=doc.title, body=doc.raw_text,
                              published_at=doc.published_at, has_author=bool(doc.author))
        m = _meta(doc)
        assert PROVENANCE_KEYS <= set(m)
        assert doc.priority_status == "RULES_ONLY"
        assert m["priority_decision_source"] == "rules"
        assert m["priority_score_source"] == "rules"
        assert doc.priority_score == expected.score
        assert m["priority_confidence"] == expected.confidence
        assert m["rules_priority_confidence"] == expected.confidence
        assert m["ai_priority_confidence"] is None
        assert m["ai_priority_reason"] is None
        assert m["ai_priority_reason_codes"] is None
        assert doc.priority_reason.startswith("rules score=")
    finally:
        session.close()


# --- ۲) Source Bot با تصمیم قواعد: همان قرارداد ---
def test_bot_rules_path_records_same_contract(monkeypatch) -> None:
    session = TestingSession()
    try:
        s = _src(session, "prov-bot-rules")
        item = RawItem(url="https://b1.test/1", **_RULES_CONFIDENT)
        metrics = _run_bot(monkeypatch, session, s, item, ai_enabled=False)
        assert metrics.stored == 1

        doc = session.query(Document).one()
        m = _meta(doc)
        assert PROVENANCE_KEYS <= set(m)
        assert doc.priority_status == "RULES_ONLY"
        assert m["priority_decision_source"] == "rules"
        assert m["priority_score_source"] == "rules"
        assert m["priority_confidence"] == m["rules_priority_confidence"]
        assert m["rules_priority_confidence"] >= UNRELIABLE_CONFIDENCE
        assert m["ai_priority_confidence"] is None
    finally:
        session.close()


# --- ۳+۴) Source Bot با تصمیم معتبر AI: سطح از AI، امتیاز از قواعد، conf جدا ---
def test_bot_ai_decision_keeps_rules_score_and_separate_confidences(monkeypatch) -> None:
    class GoodGw:
        async def generate(self, req):
            return AIResponse(text=json.dumps({"priority": "P1", "confidence": 0.82,
                                               "reason": "big event",
                                               "reason_codes": ["HIGH_IMPACT"]}),
                              provider="t", model="m", is_mock=False)

    session = TestingSession()
    try:
        s = _src(session, "prov-bot-ai")
        item = RawItem(url="https://b2.test/1", **_NEEDS_AI)
        expected = score_item(title=item.title, body=item.raw_text)
        assert expected.needs_ai is True and expected.confidence != 0.82  # پیش‌شرط تفکیک

        metrics = _run_bot(monkeypatch, session, s, item, ai_enabled=True, gw=GoodGw())
        doc = session.query(Document).one()
        m = _meta(doc)
        assert metrics.ai_used == 1
        assert doc.ingestion_priority == "P1" and doc.priority_status == "AI_DECIDED"
        assert doc.priority_score == expected.score          # امتیاز قواعد دست‌نخورده
        assert m["priority_decision_source"] == "ai"
        assert m["priority_confidence"] == 0.82
        assert m["ai_priority_confidence"] == 0.82
        assert m["rules_priority_confidence"] == expected.confidence
        assert m["ai_priority_reason"] == "big event"
        assert m["ai_priority_reason_codes"] == ["HIGH_IMPACT"]
        assert m["priority_score_source"] == "rules"
    finally:
        session.close()


# --- ۵) پاسخ AI نامعتبر/بدون confidence: هیچ مقدار جعلی، fallback فعلی ---
def test_bot_invalid_ai_response_keeps_rules_without_fake_confidence(monkeypatch) -> None:
    class BadGw:
        async def generate(self, req):
            return AIResponse(text='{"priority": "P9", "confidence": 99}',
                              provider="t", model="m", is_mock=False)

    session = TestingSession()
    try:
        s = _src(session, "prov-bot-bad-ai")
        item = RawItem(url="https://b3.test/1", **_RULES_CONFIDENT)
        metrics = _run_bot(monkeypatch, session, s, item, ai_enabled=True, gw=BadGw())

        doc = session.query(Document).one()
        m = _meta(doc)
        assert metrics.ai_fallback == 1 and metrics.ai_used == 0
        assert doc.priority_status == "RULES_FALLBACK_AI_UNAVAILABLE"
        assert m["priority_decision_source"] == "rules"
        assert m["ai_priority_confidence"] is None
        assert m["ai_priority_reason"] is None
        assert m["ai_priority_reason_codes"] is None
        assert m["priority_confidence"] == m["rules_priority_confidence"]
    finally:
        session.close()


# --- ۶) حالت mock: هرگز تصمیم واقعی AI ثبت نمی‌شود ---
def test_bot_mock_ai_is_not_recorded_as_real_decision(monkeypatch) -> None:
    class MockGw:
        async def generate(self, req):
            return AIResponse(text=json.dumps({"priority": "P0", "confidence": 0.95,
                                               "reason": "mock says P0",
                                               "reason_codes": ["MOCK"]}),
                              provider="mock", model="mock", is_mock=True)

    session = TestingSession()
    try:
        s = _src(session, "prov-bot-mock")
        item = RawItem(url="https://b4.test/1", **_RULES_CONFIDENT)
        metrics = _run_bot(monkeypatch, session, s, item, ai_enabled=True, gw=MockGw())

        doc = session.query(Document).one()
        m = _meta(doc)
        assert metrics.ai_fallback == 1 and metrics.ai_used == 0
        assert doc.priority_status == "RULES_MOCK_AI"
        assert doc.ingestion_priority != "P0"          # mock اعمال نشده
        assert m["priority_decision_source"] == "rules"
        assert m["ai_priority_confidence"] is None
        assert m["ai_priority_reason"] is None
        assert m["priority_confidence"] == m["rules_priority_confidence"]
    finally:
        session.close()


# --- ۳ب) قواعد کم‌اطمینان در Source Bot: به‌عنوان تصمیم قطعی گزارش نمی‌شود ---
def test_bot_rules_low_confidence_is_not_reported_as_decided(monkeypatch) -> None:
    """AI غیرفعال + قواعد کم‌اطمینان: منشأ pending (نه rules)، سطح/امتیاز قواعد حفظ."""
    session = TestingSession()
    try:
        s = _src(session, "prov-bot-lowconf")
        item = RawItem(url="https://b5.test/1", **_NEEDS_AI)
        expected = score_item(title=item.title, body=item.raw_text)
        assert expected.confidence < UNRELIABLE_CONFIDENCE      # پیش‌شرط سناریو

        metrics = _run_bot(monkeypatch, session, s, item, ai_enabled=False)
        doc = session.query(Document).one()
        m = _meta(doc)
        assert metrics.ai_used == 0 and metrics.ai_fallback == 0
        assert doc.ingestion_priority == expected.level          # سطح قواعد حفظ می‌شود
        assert doc.priority_score == expected.score              # امتیاز قواعد حفظ می‌شود
        assert m["priority_decision_source"] == "pending"
        assert m["priority_confidence"] is None
        assert m["rules_priority_confidence"] == expected.confidence
        assert m["ai_priority_confidence"] is None
    finally:
        session.close()


def test_bot_ai_unavailable_low_confidence_keeps_cause_and_marks_pending(monkeypatch) -> None:
    """AI unavailable + قواعد کم‌اطمینان: علت عملیاتی حفظ، تصمیم نهایی pending."""
    class DeadGw:
        async def generate(self, req):
            raise TimeoutError("provider down")

    session = TestingSession()
    try:
        s = _src(session, "prov-bot-unavail")
        item = RawItem(url="https://b6.test/1", **_NEEDS_AI)
        expected = score_item(title=item.title, body=item.raw_text)
        assert expected.confidence < UNRELIABLE_CONFIDENCE

        metrics = _run_bot(monkeypatch, session, s, item, ai_enabled=True, gw=DeadGw())
        doc = session.query(Document).one()
        m = _meta(doc)
        assert metrics.ai_fallback == 1 and metrics.ai_used == 0
        assert doc.priority_status == "RULES_FALLBACK_AI_UNAVAILABLE"   # علت حذف نشده
        assert m["priority_decision_source"] == "pending"
        assert m["priority_confidence"] is None
        assert m["rules_priority_confidence"] == expected.confidence
        assert m["ai_priority_confidence"] is None
    finally:
        session.close()


def test_bot_mock_low_confidence_keeps_cause_and_marks_pending(monkeypatch) -> None:
    """mock schema-valid + قواعد کم‌اطمینان: منشأ mock حفظ، تصمیم واقعی AI ساخته نمی‌شود."""
    class MockGw:
        async def generate(self, req):
            return AIResponse(text=json.dumps({"priority": "P0", "confidence": 0.95,
                                               "reason": "m", "reason_codes": ["MOCK"]}),
                              provider="mock", model="mock", is_mock=True)

    session = TestingSession()
    try:
        s = _src(session, "prov-bot-mock-low")
        item = RawItem(url="https://b7.test/1", **_NEEDS_AI)
        metrics = _run_bot(monkeypatch, session, s, item, ai_enabled=True, gw=MockGw())
        doc = session.query(Document).one()
        m = _meta(doc)
        assert metrics.ai_fallback == 1 and metrics.ai_used == 0
        assert doc.priority_status == "RULES_MOCK_AI"                    # علت حذف نشده
        assert doc.ingestion_priority != "P0"
        assert m["priority_decision_source"] == "pending"
        assert m["priority_confidence"] is None
        assert m["ai_priority_confidence"] is None and m["ai_priority_reason"] is None
    finally:
        session.close()


# --- ۷) PRIORITY_PENDING: تصمیم قطعی جعلی و confidence ساختگی ثبت نمی‌شود ---
def test_pending_status_records_no_final_confidence() -> None:
    session = TestingSession()
    try:
        s = _src(session, "prov-pending")
        item = RawItem(title="inflation disputed", url="https://pd.test/1", raw_text=None)
        expected = score_item(title=item.title, body=None, published_at=None, has_author=False)
        assert expected.confidence < UNRELIABLE_CONFIDENCE        # پیش‌شرط سناریو

        assert NewsIngestionPipeline(session).store_item(s, item) is True
        doc = session.query(Document).one()
        m = _meta(doc)
        assert doc.priority_status == "PRIORITY_PENDING"
        assert m["priority_decision_source"] == "pending"
        assert m["priority_confidence"] is None
        assert m["rules_priority_confidence"] == expected.confidence
        assert m["ai_priority_confidence"] is None
    finally:
        session.close()


def test_provenance_helper_never_invents_values() -> None:
    pending = priority_provenance(rules_confidence=0.1)
    assert pending["priority_decision_source"] == "pending"
    assert pending["priority_confidence"] is None
    assert pending["rules_priority_confidence"] == 0.1
    # آستانه: بالا/روی مرز = تصمیم قطعی قواعد، پایین‌تر = pending
    assert priority_provenance(rules_confidence=UNRELIABLE_CONFIDENCE)[
        "priority_decision_source"] == "rules"
    assert priority_provenance(rules_confidence=UNRELIABLE_CONFIDENCE - 0.01)[
        "priority_decision_source"] == "pending"
    assert priority_provenance(rules_confidence=None)["priority_decision_source"] == "pending"
    # پاسخ mock/invalid هرگز به‌عنوان تصمیم پذیرفته‌شده ثبت نمی‌شود (ai=None از runner)
    no_payload = priority_provenance(rules_confidence=0.4)
    assert no_payload["priority_decision_source"] == "rules"
    assert no_payload["ai_priority_confidence"] is None


# --- ۸) reason codes قواعد و AI قابل تفکیک ---
def test_rules_and_ai_reason_codes_stay_separate() -> None:
    rules = priority_provenance(rules_confidence=0.9)
    assert rules["ai_priority_reason_codes"] is None
    ai = priority_provenance(rules_confidence=0.2,
                             ai={"priority": "P1", "confidence": 0.8, "reason": "r",
                                 "reason_codes": ["HIGH_IMPACT"]})
    assert ai["ai_priority_reason_codes"] == ["HIGH_IMPACT"]
    assert "URGENT_KEYWORD" not in ai["ai_priority_reason_codes"]


# --- ۹) re-ingest و dedup: هویت و provenance قبلی خراب نمی‌شوند ---
def test_reingest_keeps_identity_and_provenance() -> None:
    session = TestingSession()
    try:
        s = _src(session, "prov-reingest")
        item = RawItem(title="Same story", url="https://r.test/1", raw_text="body text here")
        pipeline = NewsIngestionPipeline(session)
        assert pipeline.store_item(s, item) is True
        doc = session.query(Document).one()
        before = (doc.hash, doc.content_hash, doc.external_id, _meta(doc))

        assert pipeline.store_item(s, item) is False          # تکراری درون منبع
        session.expire_all()
        doc = session.query(Document).one()
        assert (doc.hash, doc.content_hash, doc.external_id, _meta(doc)) == before
        assert before[3]["priority_decision_source"] in ("rules", "ai", "pending")
    finally:
        session.close()


# --- ۱۰) قراردادهای موجود (هویت payload-only و importance) دست‌نخورده ---
def test_existing_identity_and_importance_contracts_untouched() -> None:
    assert PRIORITY_BANDS == {"P0": (1, 2), "P1": (3, 4), "P2": (5, 6),
                              "P3": (7, 8), "P4": (9, 10)}
    assert payload_hash('{"b": 2, "a": 1}') == payload_hash('{"a": 1, "b": 2}')
    assert payload_hash("{}") is None
    assert identity_hash(None, None, '{"k": 1}') == payload_hash('{"k": 1}')
    assert identity_hash("t", "b", '{"k": 1}') == content_hash("t", "b")
    # کلیدهای جدید provenance، معنای mock/real را عوض نمی‌کنند
    assert provenance_of(json.dumps({"priority_decision_source": "rules"})) == "unknown"
    assert provenance_of(json.dumps({"mock": False, "priority_decision_source": "ai"})) == "real"
