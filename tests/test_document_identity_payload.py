"""هویت رکوردهای payload-only — رفع ادغام بی‌صدای payloadهای متفاوت.

SQLite ایزوله (conftest)، بدون شبکه/دیتابیس واقعی/AI. قراردادهای تثبیت‌شده:
- URL/title/body حاضر ⇒ همان الگوریتم قبلی هش (بدون تغییر).
- URL/title/body غایب ولی raw_payload معنادار ⇒ هش پایدار از payload (مستقل از
  ترتیب کلید) تا payloadهای متفاوت یکسان تلقی نشوند و payload یکسان تکرار نشود.
- ردیف بدون هیچ هویتی در dedup شرکت نمی‌کند و بی‌صدا با ردیف دیگری ادغام نمی‌شود.
"""
from __future__ import annotations

import asyncio
import logging

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news.fetchers import RawItem
from domains.news.ingestion import NewsIngestionPipeline
from domains.news.normalizer import (
    content_hash,
    identity_hash,
    payload_hash,
    sha256,
    url_hash,
)
from source_bot import runner as runner_module
from tests.conftest import TestingSession

PAYLOAD_A = '{"metric": "a", "value": 1}'
PAYLOAD_B = '{"metric": "b", "value": 2}'


def _src(db, name: str = "ident-src") -> Source:
    src = Source(name=name, collection_method="rss", type="rss",
                 feed_url=f"https://{name}.test/rss")
    db.add(src)
    db.commit()
    return src


def _counts(db) -> tuple[int, int]:
    return db.query(Document).count(), db.query(Article).count()


# --- A: بدون URL ولی با عنوان/متن ---
def test_url_less_with_title_and_body_is_deduped() -> None:
    db = TestingSession()
    try:
        src = _src(db)
        pipeline = NewsIngestionPipeline(db)
        item = RawItem(title="عنوان", url=None, raw_text="متن")
        assert pipeline.store_item(src, item) is True
        db.commit()
        assert pipeline.store_item(src, item) is False  # همان محتوا ⇒ تکراری
        db.commit()
        assert _counts(db) == (1, 1)
        # هش همان الگوریتم قبلی است (payload نقشی ندارد)
        assert db.query(Document).one().content_hash == content_hash("عنوان", "متن")
    finally:
        db.close()


# --- B: بدون URL/title/body/external_id، فقط payload معنادار ---
def test_payload_only_rows_distinct_payloads_survive_and_repeats_dedupe() -> None:
    db = TestingSession()
    try:
        src = _src(db)
        pipeline = NewsIngestionPipeline(db)
        first = RawItem(title=None, url=None, raw_text=None, raw_payload=PAYLOAD_A)
        other = RawItem(title=None, url=None, raw_text=None, raw_payload=PAYLOAD_B)
        assert pipeline.store_item(src, first) is True
        db.commit()
        assert pipeline.store_item(src, first) is False  # payload یکسان ⇒ تکراری
        db.commit()
        assert pipeline.store_item(src, other) is True   # payload متفاوت ⇒ رکورد مستقل
        db.commit()
        assert _counts(db) == (2, 2)
        docs = db.query(Document).all()
        assert sorted(d.raw_payload for d in docs) == sorted([PAYLOAD_A, PAYLOAD_B])
        assert len({d.content_hash for d in docs}) == 2   # هویت‌های مستقل
        assert {d.source_id for d in docs} == {src.id}    # مستقل ولی درون یک منبع
    finally:
        db.close()


# --- C: دو دیکشنری JSON هم‌ارز با ترتیب کلید متفاوت ---
def test_equivalent_json_payloads_share_one_identity() -> None:
    db = TestingSession()
    try:
        src = _src(db)
        pipeline = NewsIngestionPipeline(db)
        first = RawItem(
            title=None, url=None, raw_text=None,
            raw_payload='{"outer": {"x": 1, "y": 2}, "list": [{"k": 1}], "n": 2}',
        )
        same = RawItem(
            title=None, url=None, raw_text=None,
            raw_payload='{"n": 2, "list": [{"k": 1}], "outer": {"y": 2, "x": 1}}',
        )
        assert payload_hash(first.raw_payload) == payload_hash(same.raw_payload)
        assert pipeline.store_item(src, first) is True
        db.commit()
        assert pipeline.store_item(src, same) is False  # هم‌ارز ⇒ ردیف اضافه نمی‌شود
        db.commit()
        assert _counts(db) == (1, 1)
    finally:
        db.close()


# --- D: محتوای کاملاً خالی ---
def test_identity_less_rows_are_never_silently_merged(caplog) -> None:
    """payload بی‌هویت (`""`/`null`/`{}`/`[]`) هویتی نمی‌سازد؛ ردیف بی‌هویت در
    dedup شرکت نمی‌کند (بدون ادغام بی‌صدا) و دلیلش در لاگ قابل تشخیص است.
    حفظ ردیف خام قرارداد فعلی pipeline است (test_source_bot_priority_columns)."""
    db = TestingSession()
    try:
        src = _src(db)
        pipeline = NewsIngestionPipeline(db)
        for empty in (None, "   ", "null", "{}", "[]"):
            assert payload_hash(empty) is None
        empty_item = RawItem(title=None, url=None, raw_text=None)
        with caplog.at_level(logging.WARNING, logger="domains.news.ingestion"):
            assert pipeline.store_item(src, empty_item) is True
            db.commit()
            assert pipeline.store_item(src, empty_item) is True  # ادغام بی‌صدا نشد
            db.commit()
        messages = [r.message for r in caplog.records]
        assert sum("identity-less item" in m for m in messages) == 2
        assert db.query(Document).count() == 2
        # payloadِ متفاوت همچنان رکورد مستقل می‌گیرد (بلعیده نمی‌شود)
        assert pipeline.store_item(
            src, RawItem(title=None, url=None, raw_text=None, raw_payload=PAYLOAD_B)
        ) is True
        db.commit()
        assert _counts(db) == (3, 3)
    finally:
        db.close()


# --- E: مسیر واقعی Source Bot (نه فراخوانی دستی store_item) ---
def test_payload_only_items_reach_storage_through_the_real_runner(
    monkeypatch, caplog
) -> None:
    """payload-only با payload معنادار نباید در گیت «keyless» رد شود."""
    db = TestingSession()
    try:
        src = _src(db, "payload-src")

        async def fake_fetch(plan, settings):  # noqa: ANN001, ANN202
            return (
                [
                    RawItem(title=None, url=None, raw_text=None, raw_payload=p)
                    for p in (PAYLOAD_A, PAYLOAD_A, PAYLOAD_B)
                ],
                "", {},
            )

        monkeypatch.setenv("SOURCE_BOT_MAX_RETRIES", "0")
        monkeypatch.setenv("SOURCE_BOT_AI_ENABLED", "false")
        monkeypatch.setattr(runner_module, "_fetch_plan", fake_fetch)
        monkeypatch.setattr(runner_module, "get_session_factory", lambda: TestingSession)

        with caplog.at_level(logging.INFO):
            metrics = asyncio.run(
                runner_module.run_once(source_name="payload-src", limit_sources=10, db=db)
            )

        assert (metrics.stored, metrics.duplicates) == (2, 1)
        assert not any("keyless item skipped" in r.message for r in caplog.records)
        docs = db.query(Document).all()
        assert sorted(d.raw_payload for d in docs) == sorted([PAYLOAD_A, PAYLOAD_B])
        assert {d.source_id for d in docs} == {src.id}
        assert db.query(Article).count() == 2
    finally:
        db.close()


# --- F: اسناد معمولی دست‌نخورده ---
def test_normal_document_hashes_unchanged_by_payload_fallback() -> None:
    db = TestingSession()
    try:
        src = _src(db)
        pipeline = NewsIngestionPipeline(db)
        url = "https://example.test/a"
        assert pipeline.store_item(
            src, RawItem(title="T", url=url, raw_text="B", raw_payload='{"x": 1}')
        ) is True
        db.commit()
        doc = db.query(Document).one()
        assert doc.hash == url_hash(url) == sha256(url)
        assert doc.content_hash == content_hash("T", "B")
    finally:
        db.close()

    # payload هرگز هش سند عنوان/متن‌دار را عوض نمی‌کند
    assert identity_hash("T", "B", '{"other": 9}') == content_hash("T", "B")
    # ترتیب کلید بی‌اثر، ترتیب لیست معنادار (داده‌ی متفاوت ⇒ هش متفاوت)
    assert payload_hash('{"a": 1, "b": 2}') == payload_hash('{"b": 2, "a": 1}')
    assert payload_hash('{"a": [1, 2]}') != payload_hash('{"a": [2, 1]}')
