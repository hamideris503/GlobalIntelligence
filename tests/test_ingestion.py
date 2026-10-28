"""Tests for the news ingestion pipeline (Phase 8)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.database import models as _models
from backend.database.models.source import Source
from domains.news.fetchers import MockFetcher, RawItem
from domains.news.ingestion import UNRELIABLE_CONFIDENCE, NewsIngestionPipeline
from domains.news.normalizer import clean_text, content_hash, detect_language, normalize
from source_bot.priority_engine import LEVELS, score_item
from tests.conftest import TestingSession


def _make_source() -> str:
    session = TestingSession()
    try:
        s = Source(name="Mock Source", domain="example.local", type="rss", active=True)
        session.add(s)
        session.commit()
        return str(s.id)
    finally:
        session.close()


# --- normalizer ---
def test_clean_text_strips_html() -> None:
    assert clean_text("<p>Hello <b>world</b></p>") == "Hello world"


def test_detect_language_persian() -> None:
    assert detect_language("سلام دنیا") == "fa"
    assert detect_language("hello world") == "en"


def test_content_hash_stable() -> None:
    assert content_hash("a", "b") == content_hash("a", "b")
    assert content_hash("a", "b") != content_hash("a", "c")


def test_normalize_point_in_time() -> None:
    item = RawItem(title="T", url="http://x", raw_text="Body")
    norm = normalize(item)
    assert norm.retrieved_at is not None
    assert norm.available_at is not None
    assert norm.observed_at is not None
    assert norm.content_hash is not None


# --- pipeline ---
def test_pipeline_stores_documents() -> None:
    _make_source()
    session = TestingSession()
    try:
        source = session.query(Source).first()
        pipeline = NewsIngestionPipeline(session, fetcher=MockFetcher())
        result = pipeline.ingest_source(source, limit=10)
        assert result.stored == 3
        assert result.fetched == 3
        assert session.query(_models.Document).count() == 3
        assert session.query(_models.Article).count() == 3
    finally:
        session.close()


def test_pipeline_deduplicates() -> None:
    _make_source()
    session = TestingSession()
    try:
        source = session.query(Source).first()
        pipeline = NewsIngestionPipeline(session, fetcher=MockFetcher())
        pipeline.ingest_source(source, limit=10)
        result2 = pipeline.ingest_source(source, limit=10)
        assert result2.stored == 0
        assert result2.duplicates == 3
    finally:
        session.close()


def test_same_item_from_two_sources_stored_twice() -> None:
    """یک آیتمِ واحد از دو منبع مختلف → هر دو سند ذخیره می‌شوند (P0-3)."""
    from backend.database.models.document import Document

    session = TestingSession()
    try:
        s1 = Source(name="Src A", domain="a.local", type="rss", active=True)
        s2 = Source(name="Src B", domain="b.local", type="rss", active=True)
        session.add_all([s1, s2])
        session.commit()

        pipeline = NewsIngestionPipeline(session, fetcher=MockFetcher())
        r1 = pipeline.ingest_source(s1, limit=10)
        r2 = pipeline.ingest_source(s2, limit=10)

        assert r1.stored == 3
        assert r2.stored == 3
        # هر ۳ آیتم از هر دو منبع ذخیره شده‌اند → ۶ سند
        assert session.query(Document).count() == 6

        # دقیقاً همان content_hash باید برای هر source جداگانه ذخیره شده باشد
        first_hash = (
            session.query(Document.content_hash)
            .filter(Document.source_id == s1.id)
            .order_by(Document.created_at)
            .first()[0]
        )
        same = (
            session.query(Document)
            .filter(
                Document.content_hash == first_hash,
                Document.source_id == s2.id,
            )
            .count()
        )
        assert same == 1
    finally:
        session.close()


# --- API ---
def test_ingest_api(client: TestClient) -> None:
    sid = _make_source()
    res = client.post("/api/ingest", json={"source_id": sid, "limit": 5})
    assert res.status_code == 200
    body = res.json()
    assert body["stored"] == 3

    docs = client.get("/api/ingest/documents")
    assert docs.status_code == 200
    assert len(docs.json()) == 3


def test_ingest_unknown_source_404(client: TestClient) -> None:
    res = client.post("/api/ingest", json={"source_name": "nope"})
    assert res.status_code == 404


def test_ingest_all_mock_override(client: TestClient, monkeypatch) -> None:
    """E2E: mock=false صریح، fetcher واقعی و فیلتر rss را تحمیل می‌کند (بدون شبکه)."""
    import domains.news.fetchers as fetchers_mod

    seen: dict = {}

    class _RSS:
        name = "rss"

        async def fetch(self, *, url, limit=20):
            seen["url"] = url
            return []

    # ایمپورت داخل تابعی endpoint است؛ پچ روی ماژول fetchers اثر می‌کند
    monkeypatch.setattr(fetchers_mod, "RSSFetcher", lambda **kw: _RSS())
    created = client.post("/api/sources", json={
        "name": "RSST", "type": "rss", "collection_method": "rss",
        "feed_url": "https://example.com/feed", "active": True})
    assert created.status_code == 201
    res = client.post("/api/ingest/all?limit=5&mock=false")
    assert res.status_code == 200
    assert seen.get("url") == "https://example.com/feed"  # fetcher واقعی صدا زده شد


def test_rss_fetcher_ssrf_refused() -> None:
    """فید خصوصی/داخلی بدون هیچ اتصالی رد می‌شود (census §7)."""
    import asyncio

    import pytest

    from domains.news.fetchers import RSSFetcher

    for bad in ("http://localhost:9/feed", "http://127.0.0.1/feed",
                "http://10.0.0.5/feed", "http://169.254.169.254/x"):
        with pytest.raises(ValueError, match="non-public"):
            asyncio.run(RSSFetcher().fetch(url=bad))


def test_rss_fetcher_retry_then_success(monkeypatch) -> None:
    """timeout اول → یک retry → موفقیت (بدون شبکه‌ی واقعی)."""
    import asyncio

    import httpx

    from domains.news import fetchers as fetchers_mod
    from domains.news.fetchers import RSSFetcher

    rss = (b'<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>'
           b'<item><title>A</title><link>https://x.local/1</link></item>'
           b'</channel></rss>')
    calls = {"n": 0}

    class _Resp:
        status_code = 200
        headers: dict = {}
        url = "https://example.com/feed"

        def __init__(self, content: bytes):
            self.content = content

        def raise_for_status(self) -> None:
            pass

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.TimeoutException("slow")
            return _Resp(rss)

    monkeypatch.setattr(fetchers_mod.httpx, "AsyncClient", _Client)
    items = asyncio.run(RSSFetcher().fetch(url="https://example.com/feed"))
    assert calls["n"] == 2
    assert len(items) == 1 and items[0].title == "A"


# --- اولویت P0..P4 روی مسیرهای عادی ingestion (Phase 1) ---
VALID_STATUSES = {"RULES_ONLY", "PRIORITY_PENDING"}


def _docs() -> list:
    session = TestingSession()
    try:
        return session.query(_models.Document).all()
    finally:
        session.close()


def _aware(dt):
    """sqlite زمان timezone-aware را naive برمی‌گرداند؛ فقط اثر محیط تست."""
    from datetime import UTC

    return dt.replace(tzinfo=UTC) if dt is not None and dt.tzinfo is None else dt


def test_ingest_api_persists_priority(client: TestClient) -> None:
    """بعد از /api/ingest، اولویت معتبر و هم‌ارزِ موتور موجود روی رکورد است."""
    sid = _make_source()
    assert client.post("/api/ingest", json={"source_id": sid, "limit": 5}).json()["stored"] == 3

    docs = _docs()
    assert len(docs) == 3
    for d in docs:
        expected = score_item(title=d.title, body=d.raw_text,
                              published_at=_aware(d.published_at), has_author=bool(d.author))
        assert d.ingestion_priority in LEVELS
        assert d.ingestion_priority == expected.level
        assert d.priority_score == expected.score
        assert 0.0 <= d.priority_score <= 100.0
        assert d.priority_source == "rules"
        assert d.priority_status in VALID_STATUSES
        assert d.priority_reason.startswith("rules score=")


def test_documents_api_exposes_priority(client: TestClient) -> None:
    """قرارداد مستند ربات: اولویت روی documents است، پس خواندن سند باید همان را بدهد.

    پیش از رفع، `GET /api/ingest/documents` این پنج ستون را حذف می‌کرد و
    اولویت P0..P4 از مسیر API قابل مشاهده نبود (فقط در DB).
    """
    sid = _make_source()
    assert client.post("/api/ingest", json={"source_id": sid, "limit": 5}).json()["stored"] == 3

    res = client.get("/api/ingest/documents?limit=10")
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) == 3
    for row in rows:
        assert row["ingestion_priority"] in LEVELS
        assert row["priority_source"] == "rules"
        assert row["priority_status"] in VALID_STATUSES
        assert isinstance(row["priority_score"], float)
        assert row["priority_reason"].startswith("rules score=")


def test_ingest_all_persists_priority_for_new_rows(client: TestClient) -> None:
    """همه‌ی رکوردهای جدید مسیر /api/ingest/all وضعیت اولویت صریح دارند."""
    _make_source()
    created = client.post("/api/sources", json={
        "name": "AllSrc", "type": "rss", "collection_method": "rss",
        "feed_url": "https://example.com/feed", "active": True})
    assert created.status_code == 201
    assert client.post("/api/ingest/all?limit=5").status_code == 200

    docs = _docs()
    assert len(docs) == 6  # دو منبع × سه آیتم نمونه؛ هر منبع رکورد جدا (بند ۱۸)
    for d in docs:
        assert d.ingestion_priority in LEVELS
        assert d.priority_status in VALID_STATUSES


def test_priority_contract_matches_classifier(client: TestClient) -> None:
    """قرارداد موجود classifier: همان سطح/منشأیی که صف و گیت کم‌اهمیت می‌خوانند."""
    from domains.news.classifier import _doc_priority, low_priority_level

    sid = _make_source()
    client.post("/api/ingest", json={"source_id": sid, "limit": 5})
    session = TestingSession()
    try:
        art = session.query(_models.Article).first()
        level, source = _doc_priority(art)
        assert level in LEVELS and source == "rules"
        assert low_priority_level(art) == (level if level in ("P3", "P4") else None)
    finally:
        session.close()


def test_priority_uses_existing_engine(monkeypatch) -> None:
    """منطق امتیازدهی موازی ساخته نشده: همان score_item صدا زده می‌شود."""
    import source_bot.priority_engine as pe

    real, calls = pe.score_item, []
    monkeypatch.setattr(pe, "score_item", lambda **kw: (calls.append(kw), real(**kw))[1])

    _make_source()
    session = TestingSession()
    try:
        NewsIngestionPipeline(session, fetcher=MockFetcher()).ingest_source(
            session.query(Source).one())
    finally:
        session.close()
    assert len(calls) == 3


def test_existing_priority_not_recomputed() -> None:
    """اولویت تصمیم‌گرفته‌شده‌ی source_bot بازنویسی نمی‌شود (سیگنال کم، تصمیم P0)."""
    from source_bot.output import deliver

    session = TestingSession()
    try:
        s = Source(name="keep", domain="k.local", type="rss", active=True)
        session.add(s)
        session.commit()
        assert deliver(session, s, RawItem(title="x", url="https://k.local/1", raw_text="y"),
                       priority="P0", score=95.0, reason="rules score=95.0",
                       priority_source="rules", priority_status="RULES_ONLY",
                       duplicate_status="new") is True
        doc = session.query(_models.Document).one()
        assert (doc.ingestion_priority, doc.priority_score) == ("P0", 95.0)
        assert doc.priority_status == "RULES_ONLY"
    finally:
        session.close()


def test_priority_failure_keeps_raw_document(client: TestClient, monkeypatch) -> None:
    """شکست اولویت‌بندی نه سند خام را حذف می‌کند و نه ingestion را می‌شکند."""
    import source_bot.priority_engine as pe

    def _boom(**kw):
        raise RuntimeError("scorer down")

    monkeypatch.setattr(pe, "score_item", _boom)
    sid = _make_source()
    res = client.post("/api/ingest", json={"source_id": sid, "limit": 5})
    assert res.status_code == 200 and res.json()["stored"] == 3

    docs = _docs()
    assert len(docs) == 3
    for d in docs:
        assert d.ingestion_priority is None and d.priority_score is None
        assert d.raw_payload and d.retrieved_at and d.available_at and d.observed_at


def test_unreliable_item_records_explicit_pending_status() -> None:
    """داده‌ی ناقص/متعارض با confidence پایین: امتیاز صادق + وضعیت صریح عدم‌قطعیت."""
    item = RawItem(title="inflation disputed", url="https://p.local/1", raw_text=None)
    expected = score_item(title=item.title, body=None, published_at=None, has_author=False)
    assert expected.confidence < UNRELIABLE_CONFIDENCE  # پیش‌شرط سناریو

    session = TestingSession()
    try:
        s = Source(name="pending", domain="p.local", type="rss", active=True)
        session.add(s)
        session.commit()
        assert NewsIngestionPipeline(session).store_item(s, item) is True
        doc = session.query(_models.Document).one()
        assert (doc.ingestion_priority, doc.priority_score) == (expected.level, expected.score)
        assert doc.priority_source == "rules"
        assert doc.priority_status == "PRIORITY_PENDING"
    finally:
        session.close()


def test_broken_source_does_not_block_others() -> None:
    """منبع خراب (fetch استثنا) مانع ذخیره‌ی منبع سالم روی همان session نمی‌شود."""
    class _Flaky:
        name = "flaky"

        async def fetch(self, *, url=None, limit=20):
            if url and "bad" in url:
                raise RuntimeError("source down")
            return [RawItem(title="Good item", url="https://g.local/1", raw_text="body")]

    session = TestingSession()
    try:
        good = Source(name="good", domain="good.local", type="rss", active=True,
                      feed_url="https://good.local/feed")
        bad = Source(name="bad", domain="bad.local", type="rss", active=True,
                     feed_url="https://bad.local/feed")
        session.add_all([good, bad])
        session.commit()
        pipeline = NewsIngestionPipeline(session, fetcher=_Flaky())
        assert pipeline.ingest_source(bad).stored == 0
        ok = pipeline.ingest_source(good)
        assert ok.stored == 1 and ok.errors == []
        doc = session.query(_models.Document).one()
        assert doc.ingestion_priority in LEVELS and doc.priority_source == "rules"
    finally:
        session.close()


def test_plain_ingest_never_calls_ai(monkeypatch) -> None:
    """مسیر عادی ingestion هیچ فراخوانی Gateway/AI ندارد (قطعی)."""
    def _boom():
        raise AssertionError("AI gateway must not be called on the plain ingestion path")

    monkeypatch.setattr("backend.ai.gateway.get_gateway", _boom)
    _make_source()
    session = TestingSession()
    try:
        assert NewsIngestionPipeline(session, fetcher=MockFetcher()).ingest_source(
            session.query(Source).one()).stored == 3
    finally:
        session.close()


def test_no_double_store_across_ingest_paths() -> None:
    """مسیر عادی و مسیر ربات روی یک کلید یکتا converge می‌کنند (dedup متناقض نداریم)."""
    from source_bot.output import deliver

    session = TestingSession()
    try:
        plain = Source(name="plain-first", domain="p.local", type="rss", active=True)
        bot = Source(name="bot-first", domain="b.local", type="rss", active=True)
        session.add_all([plain, bot])
        session.commit()
        item = RawItem(title="Same story", url="https://x.local/1", raw_text="Body text")
        dl = dict(priority="P2", score=50.0, reason="rules score=50.0",
                  priority_source="rules", priority_status="RULES_ONLY",
                  duplicate_status="new", canonical_url="https://x.local/1",
                  final_url="https://x.local/1", external_id="ext-1")

        # ۱) عادی → ربات: رکورد دوم ساخته نمی‌شود
        assert NewsIngestionPipeline(session).store_item(plain, item) is True
        assert deliver(session, plain, item, **dl) is False

        # ۲) ربات → عادی: همان کلید یکتا؛ provenance ربات روی رکورد محفوظ می‌ماند
        assert deliver(session, bot, item, **dl) is True
        assert NewsIngestionPipeline(session).store_item(bot, item) is False

        assert session.query(_models.Document).filter_by(source_id=plain.id).count() == 1
        docs = session.query(_models.Document).filter_by(source_id=bot.id).all()
        assert len(docs) == 1
        assert (docs[0].ingestion_priority, docs[0].canonical_url, docs[0].external_id) == (
            "P2", "https://x.local/1", "ext-1")
    finally:
        session.close()


def test_ingest_api_dedup_and_provenance_preserved(client: TestClient) -> None:
    """تکرار دقیق و provenance مسیر عادی دست‌نخورده مانده است."""
    sid = _make_source()
    assert client.post("/api/ingest", json={"source_id": sid, "limit": 5}).json()["stored"] == 3
    second = client.post("/api/ingest", json={"source_id": sid, "limit": 5}).json()
    assert second["stored"] == 0 and second["duplicates"] == 3
    assert len(_docs()) == 3


# --- provenance contract at the storage boundary (مرحلهٔ ۳۳) ---

def test_store_item_flags_missing_provenance_without_claiming_real(caplog) -> None:
    """metadata بدون فلگ: نشانهٔ صریح + هشدار، نه ادعای real و نه توقف ingestion."""
    import json

    from backend.database.models.document import provenance_of

    session = TestingSession()
    try:
        s = Source(name="no-flag", domain="nf.local", type="rss", active=True)
        session.add(s)
        session.commit()
        item = RawItem(title="No flag", url="https://nf.local/1", raw_text="body text")
        with caplog.at_level("WARNING", logger="domains.news.ingestion"):
            assert NewsIngestionPipeline(session).store_item(s, item) is True
        doc = session.query(_models.Document).one()
        meta = json.loads(doc.doc_metadata)
        assert meta["provenance_missing"] is True and "mock" not in meta
        assert provenance_of(doc.doc_metadata) == "unknown"   # حدس real/mock ممنوع
        assert any("provenance missing" in r.getMessage() for r in caplog.records)
    finally:
        session.close()


def test_provenance_flag_does_not_change_identity_or_revision() -> None:
    """افزودن کلید provenance هویت خبر را عوض نمی‌کند (هش/ریویژن یکسان)."""
    base = {"title": "Same story", "url": "https://p.local/same", "raw_text": "Body text"}
    flagged = normalize(RawItem(**base, metadata={"mock": False}))
    unflagged = normalize(RawItem(**base))
    assert (flagged.hash, flagged.content_hash) == (unflagged.hash, unflagged.content_hash)

    session = TestingSession()
    try:
        s1 = Source(name="prov-a", domain="a.local", type="rss", active=True)
        s2 = Source(name="prov-b", domain="b.local", type="rss", active=True)
        session.add_all([s1, s2])
        session.commit()
        pipe = NewsIngestionPipeline(session)
        assert pipe.store_item(s1, RawItem(**base, metadata={"mock": False})) is True
        assert pipe.store_item(s2, RawItem(**base)) is True
        docs = session.query(_models.Document).all()
        assert {d.content_hash for d in docs} == {flagged.content_hash}
        assert [d.revision for d in docs] == [1, 1]
    finally:
        session.close()


def test_fixed_input_two_pass_is_idempotent_and_keeps_identity() -> None:
    """ورودی ثابت دو بار: گذر دوم نه ردیفی می‌سازد و نه هویت/revision/متادیتا را عوض می‌کند."""
    import json

    items = [
        RawItem(title=f"fixed story {i}", url=f"https://f.local/{i}",
                raw_text="central bank policy body text " * 12,
                raw_payload=f'{{"id": {i}}}',
                metadata={"mock": False, "text_status": "full_text_extracted",
                          "identity_text": f"summary {i}"})
        for i in (1, 2, 3)
    ]
    session = TestingSession()
    try:
        source = Source(name="fixed-src", domain="f.local", type="rss", active=True)
        session.add(source)
        session.commit()
        pipeline = NewsIngestionPipeline(session)

        assert [pipeline.store_item(source, item) for item in items] == [True, True, True]
        assert session.query(_models.Document).count() == 3
        assert session.query(_models.Article).count() == 3

        def snapshot() -> dict:
            session.expire_all()
            return {
                str(d.id): (d.hash, d.content_hash, d.revision, d.retrieved_at,
                            d.duplicate_status, d.raw_text, d.doc_metadata)
                for d in session.query(_models.Document).all()
            }

        before = snapshot()
        assert {row[2] for row in before.values()} == {1}

        assert [pipeline.store_item(source, item) for item in items] == [False, False, False]
        assert session.query(_models.Document).count() == 3
        assert session.query(_models.Article).count() == 3
        assert snapshot() == before
        for d in session.query(_models.Document).all():
            meta = json.loads(d.doc_metadata)
            assert meta["mock"] is False
            assert meta["text_status"] == "full_text_extracted"
    finally:
        session.close()


def test_store_item_persists_rss_and_mock_provenance() -> None:
    """ذخیرهٔ RSS واقعی ⇒ real + rss_summary_only؛ ذخیرهٔ MockFetcher ⇒ mock."""
    import asyncio
    import json
    from pathlib import Path

    from backend.database.models.document import provenance_of
    from domains.news.fetchers import TEXT_STATUS, RSSFetcher

    fixture = Path(__file__).parent / "fixtures" / "sample_atom.xml"
    rss_item = RSSFetcher().parse(fixture.read_bytes(), limit=1)[0]
    mock_item = asyncio.run(MockFetcher().fetch(url=None, limit=1))[0]

    session = TestingSession()
    try:
        s1 = Source(name="rss-prov", domain="r.local", type="rss", active=True)
        s2 = Source(name="mock-prov", domain="m.local", type="rss", active=True)
        session.add_all([s1, s2])
        session.commit()
        pipe = NewsIngestionPipeline(session)
        assert pipe.store_item(s1, rss_item) is True
        assert pipe.store_item(s2, mock_item) is True
        docs = {d.source_id: d for d in session.query(_models.Document).all()}
        rss_doc, mock_doc = docs[s1.id], docs[s2.id]
        assert provenance_of(rss_doc.doc_metadata) == "real"
        assert provenance_of(mock_doc.doc_metadata) == "mock"
        assert json.loads(rss_doc.doc_metadata)[TEXT_STATUS] == "rss_summary_only"
        assert "provenance_missing" not in json.loads(rss_doc.doc_metadata)
    finally:
        session.close()
