"""هویت خبر در برابر enrichment متن — آفلاین (fixture/mock، بدون شبکه).

قرارداد: جایگزینی خلاصهٔ RSS با متن کامل مقاله نباید خبر را به رکورد/هویت مستقل
تبدیل کند؛ و تغییر واقعی محتوای فید همان‌طور که قبلاً بود revision می‌سازد.
"""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from backend.database.models.document import Document, provenance_of
from backend.database.models.source import Source
from domains.news.fetchers import MockFetcher, RawItem, RSSFetcher
from domains.news.normalizer import (
    IDENTITY_TEXT_KEY,
    content_hash,
    identity_body,
    identity_hash,
    normalize,
)
from source_bot import runner as runner_module
from source_bot.fulltext import (
    FULL_TEXT,
    SUMMARY_ONLY,
    TEXT_STATUS,
    enrich_rss_items,
)
from tests.conftest import TestingSession

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
<item><title>Rates held</title><link>https://id-src.test/1</link>
<description>central bank kept rates unchanged</description><guid>g-1</guid>
<pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate></item>
</channel></rss>"""

RSS_S2 = RSS.replace(b"central bank kept rates unchanged", b"central bank raised rates by 25bp")

ARTICLE_HTML = (
    "<html><head><title>Rates held</title></head><body><article><h1>Rates held</h1><p>"
    + ("The central bank kept its policy rate unchanged after the meeting. " * 8)
    + "</p></article></body></html>"
)


@pytest.fixture(autouse=True)
def _isolated_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_module, "STOP_PATH", str(tmp_path / "source_bot.stop"))


def _source(db, name="id-src", *, domain=None):
    src = Source(name=name, domain=domain or f"{name}.test", collection_method="rss",
                 type="rss", feed_url=f"https://{name}.test/rss", active=True)
    db.add(src)
    db.commit()
    return src


def _wire(monkeypatch, items):
    """`_fetch_plan` جعلی؛ items می‌تواند callable باشد تا هر اجرا آیتم تازه بدهد."""

    async def fake_fetch(plan, settings):  # noqa: ANN001
        return (list(items() if callable(items) else items), "", {})

    monkeypatch.setattr(runner_module, "_fetch_plan", fake_fetch)
    monkeypatch.setenv("SOURCE_BOT_AI_ENABLED", "false")
    monkeypatch.setenv("SOURCE_BOT_DELAY", "0")


def _articles(monkeypatch, *, ok=True):
    """صفحهٔ مقاله از fixture محلی؛ ok=False یعنی استخراج شکست می‌خورد.

    robots.txt هم seam می‌شود (مرحلهٔ ۲۵): بدون آن، fetch واقعی robots در تست
    آفلاین fail-closed می‌شود و هیچ مقاله‌ای استخراج نمی‌شد.
    """
    from source_bot import fulltext as fulltext_module
    from source_bot.adapters import html as html_module

    calls: list[str] = []

    async def fake_safe_get(client, url, **kw):  # noqa: ANN001
        calls.append(url)
        if not ok:
            raise RuntimeError("article unavailable")
        return httpx.Response(200, content=ARTICLE_HTML.encode("utf-8"),
                              request=httpx.Request("GET", url))

    async def robots_allow(url: str, **kw):  # noqa: ANN001, ANN003, ANN202
        return "User-agent: *\nAllow: /\n"

    monkeypatch.setattr(html_module, "safe_get", fake_safe_get)
    monkeypatch.setattr(fulltext_module, "_guarded_robots", robots_allow)
    return calls


def _run(name, db, **kw):
    return asyncio.run(runner_module.run_once(source_name=name, db=db, **kw))


def _docs(db):
    return db.query(Document).order_by(Document.revision).all()


async def _robots_allow(url: str, **kw):  # noqa: ANN001, ANN003, ANN202
    """seam آفلاین robots.txt برای فراخوان مستقیم `enrich_rss_items`."""
    return "User-agent: *\nAllow: /\n"


# --- هویت: واحد ---

def test_identity_body_presence_rules():
    assert identity_body("current", None) == "current"
    assert identity_body("current", {}) == "current"
    assert identity_body("full text", {IDENTITY_TEXT_KEY: "summary"}) == "summary"
    assert identity_body("full text", {IDENTITY_TEXT_KEY: ""}) == ""       # تهی هم لنگر است
    assert identity_body("full text", {IDENTITY_TEXT_KEY: 5}) is None      # نوع نامعتبر = خالی


def test_normalize_uses_declared_anchor():
    summary, full = "short summary", ("full article text " * 20).strip()
    a = normalize(RawItem(title="T", url="https://x.test/1", raw_text=summary,
                          raw_payload='{"g":"1"}'))
    b = normalize(RawItem(title="T", url="https://x.test/1", raw_text=full,
                          raw_payload='{"g":"1"}', metadata={IDENTITY_TEXT_KEY: summary}))
    assert a.raw_text == summary and b.raw_text == full       # متن ذخیره‌شده عوض می‌شود
    assert b.content_hash == content_hash("T", summary)       # هویت عوض نمی‌شود
    assert a.content_hash == b.content_hash


def test_empty_summary_anchor_matches_missing_text():
    """مرحلهٔ ۲۹: با خلاصهٔ غایب/تهی، هویت روی URL لنگر می‌گیرد (نه عنوان تنها)."""
    url = "https://x.test/1"
    a = normalize(RawItem(title="T", url=url, raw_text=None))
    b = normalize(RawItem(title="T", url=url, raw_text="full body " * 10,
                          metadata={IDENTITY_TEXT_KEY: ""}))
    assert a.content_hash == b.content_hash == identity_hash("T", None, None, url)
    assert a.content_hash != content_hash("T", None)  # رفتار قبلی (عنوان‌محور) دیگر رخ نمی‌دهد


def test_enrich_sets_anchor_only_on_replacement():
    async def long_fetch(url: str):
        return type("R", (), {"items": [RawItem(title="t", url=url, raw_text="x " * 200)]})()

    async def short_fetch(url: str):
        return type("R", (), {"items": [RawItem(title="t", url=url, raw_text="tiny")]})()

    item = RawItem(title="t", url="https://articles.example/1", raw_text="rss summary")
    asyncio.run(enrich_rss_items([item], allowed_hosts=("articles.example",), delay=0,
                                 fetch=long_fetch, robots_fetch=_robots_allow))
    assert item.metadata[IDENTITY_TEXT_KEY] == "rss summary"
    assert item.metadata[TEXT_STATUS] == FULL_TEXT

    item2 = RawItem(title="t", url="https://articles.example/2", raw_text="rss summary")
    asyncio.run(enrich_rss_items([item2], allowed_hosts=("articles.example",), delay=0,
                                 fetch=short_fetch, robots_fetch=_robots_allow))
    assert IDENTITY_TEXT_KEY not in item2.metadata
    assert item2.metadata[TEXT_STATUS] == SUMMARY_ONLY


def test_existing_unique_indexes_unchanged():
    names = {c.name for c in Document.__table__.constraints}
    names |= {i.name for i in Document.__table__.indexes}
    assert {"uq_document_source_url_content", "uq_documents_source_external_id",
            "uq_documents_source_content_hash_ridless"} <= names


# --- runner: خلاصه → متن کامل ---

def test_enrichment_after_summary_creates_no_second_document(monkeypatch):
    db = TestingSession()
    try:
        _source(db)
        _wire(monkeypatch, lambda: RSSFetcher().parse(RSS, limit=5))
        _articles(monkeypatch, ok=False)                      # اجرای ۱: فقط خلاصه
        m1 = _run("id-src", db)
        assert m1.stored == 1 and db.query(Document).count() == 1
        doc = db.query(Document).one()
        assert doc.raw_text == "central bank kept rates unchanged" and doc.revision == 1

        _articles(monkeypatch, ok=True)                       # اجرای ۲: متن کامل
        m2 = _run("id-src", db)
        assert m2.stored == 0 and m2.duplicates == 1
        assert m2.stored == sum(m2.by_priority.values())      # شمارنده‌ها سازگار
        docs = _docs(db)
        assert len(docs) == 1 and docs[0].revision == 1
        assert docs[0].raw_text == "central bank kept rates unchanged"  # متن قبلی حفظ شد
    finally:
        db.close()


def test_fallback_after_enrichment_is_duplicate(monkeypatch):
    db = TestingSession()
    try:
        _source(db)
        _wire(monkeypatch, lambda: RSSFetcher().parse(RSS, limit=5))
        _articles(monkeypatch, ok=True)                       # اجرای ۱: متن کامل
        m1 = _run("id-src", db)
        assert m1.stored == 1
        full = db.query(Document).one().raw_text
        assert full and len(full) > 200

        _articles(monkeypatch, ok=False)                      # اجرای ۲: خلاصه (fallback)
        m2 = _run("id-src", db)
        assert m2.stored == 0 and m2.duplicates == 1
        docs = _docs(db)
        assert len(docs) == 1 and docs[0].revision == 1
        assert docs[0].raw_text == full                       # متن کامل دست‌نخورده
    finally:
        db.close()


def test_repeated_enrichment_is_idempotent(monkeypatch):
    db = TestingSession()
    try:
        _source(db)
        _wire(monkeypatch, lambda: RSSFetcher().parse(RSS, limit=5))
        _articles(monkeypatch, ok=True)
        assert _run("id-src", db).stored == 1
        m2 = _run("id-src", db)
        assert m2.stored == 0 and m2.duplicates == 1
        assert db.query(Document).count() == 1
    finally:
        db.close()


def test_empty_summary_enrichment_stays_single_document(monkeypatch):
    db = TestingSession()
    try:
        _source(db)

        def items():
            return [RawItem(title="Rates held", url="https://id-src.test/2", raw_text=None,
                            raw_payload='{"id": "g-2"}')]

        _wire(monkeypatch, items)
        _articles(monkeypatch, ok=True)                       # اجرای ۱: متن کامل، بدون خلاصه
        m1 = _run("id-src", db)
        assert m1.stored == 1
        _articles(monkeypatch, ok=False)                      # اجرای ۲: بدون متن
        m2 = _run("id-src", db)
        assert m2.stored == 0 and m2.duplicates == 1
        assert db.query(Document).count() == 1
    finally:
        db.close()


# --- runner: سیاست‌های موجود حفظ شوند ---

def test_genuine_feed_content_change_still_creates_revision(monkeypatch):
    db = TestingSession()
    try:
        _source(db)
        _wire(monkeypatch, lambda: RSSFetcher().parse(RSS, limit=5))
        _articles(monkeypatch, ok=False)
        assert _run("id-src", db).stored == 1

        _wire(monkeypatch, lambda: RSSFetcher().parse(RSS_S2, limit=5))  # همان URL، متن جدید
        m2 = _run("id-src", db)
        assert m2.stored == 1 and m2.duplicates == 0
        docs = _docs(db)
        assert len(docs) == 2 and [d.revision for d in docs] == [1, 2]
        assert docs[0].hash == docs[1].hash                    # همان URL
        assert docs[0].content_hash != docs[1].content_hash    # محتوای متفاوت
    finally:
        db.close()


def test_two_independent_urls_same_text_are_not_merged(monkeypatch):
    db = TestingSession()
    try:
        _source(db)

        def items():
            return [RawItem(title="Same", url="https://id-src.test/a", raw_text="identical body"),
                    RawItem(title="Same", url="https://id-src.test/b", raw_text="identical body")]

        _wire(monkeypatch, items)
        _articles(monkeypatch, ok=False)
        m = _run("id-src", db)
        assert m.stored == 2 and m.duplicates == 0
        assert db.query(Document).count() == 2
    finally:
        db.close()


def test_url_less_rows_keep_external_id_contract(monkeypatch):
    db = TestingSession()
    try:
        _source(db)

        def items():
            return [RawItem(title="Row A", url=None, raw_text="value a",
                            metadata={"external_id": "ind:A"}),
                    RawItem(title="Row B", url=None, raw_text="value b",
                            metadata={"external_id": "ind:B"})]

        _wire(monkeypatch, items)
        _articles(monkeypatch, ok=False)
        m1 = _run("id-src", db)
        assert m1.stored == 2
        assert {d.external_id for d in _docs(db)} == {"ind:A", "ind:B"}

        m2 = _run("id-src", db)                                # همان external_idها
        assert m2.stored == 0 and m2.duplicates == 2
        assert db.query(Document).count() == 2

        def same_ext_new_content():
            return [RawItem(title="Row A", url=None, raw_text="totally different value",
                            metadata={"external_id": "ind:A"})]

        _wire(monkeypatch, same_ext_new_content)
        m3 = _run("id-src", db)
        assert m3.stored == 0 and m3.duplicates == 1           # external_id هویت است
        assert db.query(Document).count() == 2
    finally:
        db.close()


def test_url_less_identityless_item_is_rejected_not_merged(monkeypatch):
    db = TestingSession()
    try:
        _source(db)
        _wire(monkeypatch, lambda: [RawItem(title=None, url=None, raw_text=None,
                                            raw_payload=None)])
        _articles(monkeypatch, ok=False)
        m = _run("id-src", db)
        assert m.stored == 0 and m.duplicates == 1
        assert m.by_source["id-src"].rejected_keyless == 1
        assert db.query(Document).count() == 0
    finally:
        db.close()


# --- سقف/توقف/شمارنده‌ها/provenance ---

def test_items_cap_applies_before_enrichment(monkeypatch):
    db = TestingSession()
    try:
        _source(db)

        def items():
            return [RawItem(title=f"T{i}", url=f"https://id-src.test/{i}", raw_text=f"summary {i}")
                    for i in range(3)]

        _wire(monkeypatch, items)
        calls = _articles(monkeypatch, ok=True)
        m = _run("id-src", db, max_items_per_source=1)
        assert m.fetched == 3 and m.stored == 1 and m.items_skipped_limit == 2
        assert calls == ["https://id-src.test/0"]              # فقط آیتم منتخب fetch شد
        assert db.query(Document).count() == 1
    finally:
        db.close()


def test_stop_before_run_makes_no_request(monkeypatch):
    db = TestingSession()
    try:
        _source(db)
        _wire(monkeypatch, lambda: RSSFetcher().parse(RSS, limit=5))
        calls = _articles(monkeypatch, ok=True)
        with open(runner_module.STOP_PATH, "w", encoding="utf-8") as fh:
            fh.write("stop")
        m = _run("id-src", db)
        assert m.stopped is True and m.stored == 0
        assert calls == [] and db.query(Document).count() == 0
    finally:
        db.close()


def test_enriched_metadata_keeps_provenance_and_priority(monkeypatch):
    db = TestingSession()
    try:
        _source(db)
        _wire(monkeypatch, lambda: RSSFetcher().parse(RSS, limit=5))
        _articles(monkeypatch, ok=True)
        m = _run("id-src", db)
        assert m.stored == 1
        doc = db.query(Document).one()
        meta = json.loads(doc.doc_metadata)
        assert meta[IDENTITY_TEXT_KEY] == "central bank kept rates unchanged"
        assert meta[TEXT_STATUS] == FULL_TEXT
        assert provenance_of(doc.doc_metadata) == "real"       # mock:false از پارس واقعی
        assert doc.ingestion_priority in {"P0", "P1", "P2", "P3", "P4"}
        assert doc.priority_score is not None and doc.priority_status == "RULES_ONLY"
    finally:
        db.close()


def test_provenance_not_defaulted_to_real():
    assert provenance_of(json.dumps({"guid": "g", "external_id": "x"})) == "unknown"
    item = asyncio.run(MockFetcher().fetch(url=None, limit=1))[0]
    assert provenance_of(json.dumps(item.metadata)) == "mock"


def test_old_summary_rows_keep_unknown_provenance(monkeypatch):
    """رکورد قدیمی (بدون کلید mock و بدون لنگر) دست‌نخورده و unknown می‌ماند."""
    db = TestingSession()
    try:
        src = _source(db, "legacy-src")
        legacy = Document(source_id=src.id, title="Old", raw_text="old summary",
                          hash="h-old", content_hash=content_hash("Old", "old summary"),
                          doc_metadata=json.dumps({"guid": "old"}))
        db.add(legacy)
        db.commit()
        _wire(monkeypatch, lambda: RSSFetcher().parse(RSS, limit=5))
        _articles(monkeypatch, ok=True)
        _run("legacy-src", db)
        db.refresh(legacy)
        assert legacy.raw_text == "old summary" and legacy.revision is None
        assert provenance_of(legacy.doc_metadata) == "unknown"
    finally:
        db.close()
