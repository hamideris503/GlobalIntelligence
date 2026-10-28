"""مرحلهٔ ۲۹ — هویت جایگزین برای خبرهای RSS بدون خلاصهٔ قابل‌استفاده (آفلاین، بدون شبکه).

قرارداد نهایی: وقتی بدنهٔ هویت‌بخش (خلاصهٔ RSS) تهی یا غایب است، `identity_body` یک
لنگر قطعی از URL canonical می‌سازد تا هش به «عنوان تنها» فرو نکاهد. مسیر خلاصه‌دار
(BBC / Al Jazeera)، منطق revision و ردیف‌های بدون URL دست‌نخورده می‌مانند.
"""
from __future__ import annotations

from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news.fetchers import RawItem
from domains.news.ingestion import NewsIngestionPipeline
from domains.news.normalizer import (
    IDENTITY_TEXT_KEY,
    content_hash,
    identity_body,
    identity_hash,
    identity_url_anchor,
    normalize,
)
from source_bot.deduplicator import canonical_url
from tests.conftest import TestingSession

TITLE = "Frank Elderson: From climate and nature risks to economic resilience"
SUMMARY = "central bank kept rates unchanged"
FULL = "The Governing Council kept its policy rate unchanged after the meeting. " * 6
# آدرس‌های واقعی ECB: اسلش دوتایی در مسیر و بدون پارامتر رهگیری.
URL_A = "https://www.ecb.europa.eu//press/key/date/2026/html/ecb.sp261019~f0a3e053de.en.html"
URL_B = "https://www.ecb.europa.eu//press/key/date/2026/html/ecb.sp261017~7015ea3099.en.html"


def _source(db, name="ecb-like"):
    src = Source(name=name, domain=f"{name}.test", collection_method="rss", type="rss",
                 feed_url=f"https://{name}.test/rss", active=True)
    db.add(src)
    db.commit()
    return src


def _item(url, *, title=TITLE, text=None, metadata=None):
    return RawItem(title=title, url=url, raw_text=text, metadata=dict(metadata or {}))


# --- قرارداد نرمال‌سازی URL لنگر ----------------------------------------------------


def test_identity_url_anchor_matches_canonical_url_rule() -> None:
    """لنگر همان قاعدهٔ `canonical_url` پروژه را دارد (بدون قاعدهٔ تازه)."""
    for url in (URL_A, "https://EX.com/path/", "https://ex.com/a?x=1#frag", "https://ex.com",
                "http://ex.com/a/", "ftp://ex.com/a", "not a url", "", None):
        assert identity_url_anchor(url) == canonical_url(url)
    assert identity_url_anchor("https://EX.com/path/#frag") == "https://ex.com/path"
    # مسیر «اصلاح» نمی‌شود: اسلش دوتایی فید ECB حفظ می‌شود (تغییر معنا اثبات نشده).
    assert "//press/" in identity_url_anchor(URL_A)


def test_canonicalization_failure_is_not_silent_identity_change() -> None:
    for bad in ("not a url", "ftp://ex.com/a", "", None):
        assert identity_url_anchor(bad) is None
    # بدون لنگر: همان رفتار قبلی (بدون استثنا و بدون تغییر خاموش)
    assert identity_hash(TITLE, None, None, "ftp://ex.com/a") == content_hash(TITLE, None)
    norm = normalize(RawItem(title=TITLE, url="ftp://ex.com/a", raw_text=None, metadata={}))
    assert norm.content_hash == content_hash(TITLE, None)
    assert norm.hash is not None  # رکورد نمی‌افتد


def test_titleless_row_stays_identity_less_with_url() -> None:
    """محافظ عنوان: ردیف بی‌عنوان با URL و بدنهٔ تهی هویت نمی‌سازد (قرارداد NULL قبلی)."""
    assert identity_hash(None, None, None, URL_A) is None
    assert identity_hash("   ", None, None, URL_A) is None
    assert normalize(RawItem(title=None, url=URL_A, raw_text=None, metadata={})).content_hash is None


# --- هویت خلاصه‌محور (مسیر BBC / Al Jazeera) ---------------------------------------


def test_summary_anchor_unchanged_from_summary_to_full_text() -> None:
    assert identity_body(SUMMARY, {}) == SUMMARY
    assert identity_body(FULL, {IDENTITY_TEXT_KEY: SUMMARY}) == SUMMARY
    assert identity_hash(TITLE, SUMMARY, None, URL_A) == content_hash(TITLE, SUMMARY)


def test_presence_rules_preserved_without_url() -> None:
    assert identity_body("current", None) == "current"
    assert identity_body("current", {}) == "current"
    assert identity_body("full text", {IDENTITY_TEXT_KEY: ""}) == ""
    assert identity_body("full text", {IDENTITY_TEXT_KEY: 5}) is None
    assert identity_body(None, {}) is None
    # بدون URL هیچ لنگر جانشینی ساخته نمی‌شود (سازگاری عقب‌رو)
    assert identity_hash(TITLE, None, None) == content_hash(TITLE, None)


# --- هویت لنگرشده روی URL (خلاصهٔ غایب یا تهی) -------------------------------------


def test_content_hash_is_not_title_only_for_summaryless_item() -> None:
    norm = normalize(RawItem(title=TITLE, url=URL_A, raw_text=None, metadata={}))
    assert norm.content_hash != content_hash(TITLE, None)
    assert norm.content_hash == identity_hash(TITLE, None, None, URL_A)
    assert norm.content_hash == content_hash(TITLE, identity_url_anchor(URL_A))


def test_empty_summary_same_title_two_urls_are_distinct() -> None:
    a, b = identity_hash(TITLE, None, None, URL_A), identity_hash(TITLE, None, None, URL_B)
    assert a == content_hash(TITLE, identity_url_anchor(URL_A))
    assert b == content_hash(TITLE, identity_url_anchor(URL_B))
    assert a != b


def test_absent_and_empty_description_share_one_identity() -> None:
    """رکورد غنی‌شده (لنگر تهی اعلام‌شده) و رکورد مسدودشده (بدون کلید) یک هویت دارند."""
    blocked = identity_hash(TITLE, None, None, URL_A)  # robots مسدود: بدون description
    declared_empty = identity_hash(TITLE, "", None, URL_A)  # ECB: آداپتور لنگر تهی اعلام کرد
    assert blocked == declared_empty == content_hash(TITLE, identity_url_anchor(URL_A))


def test_stable_across_runs_same_url_same_anchor() -> None:
    assert identity_url_anchor(URL_A) == identity_url_anchor(URL_A)
    assert identity_url_anchor("https://EX.com/a/") == identity_url_anchor("https://ex.com/a")
    # پارامتر رهگیری حذف نمی‌شود (قاعدهٔ مصوب = قاعدهٔ canonical_url): تفاوت فقط همان پارامتر
    base = identity_url_anchor("https://ex.com/a")
    tracked = identity_url_anchor("https://ex.com/a?utm_source=rss")
    assert tracked == "https://ex.com/a?utm_source=rss" and tracked != base


# --- round-trip روی pipeline (in-memory SQLite، بدون نوشتن در Postgres) -------------


def test_same_title_different_url_same_source_not_false_duplicate() -> None:
    db = TestingSession()
    src = _source(db)
    pipe = NewsIngestionPipeline(db)
    assert pipe.store_item(src, _item(URL_A)) is True
    assert pipe.store_item(src, _item(URL_B)) is True
    docs = db.query(Document).order_by(Document.url).all()
    assert len(docs) == 2
    assert docs[0].content_hash != docs[1].content_hash
    assert [d.revision for d in docs] == [1, 1]
    db.close()


def test_repeat_empty_summary_item_is_stable_duplicate() -> None:
    db = TestingSession()
    src = _source(db)
    pipe = NewsIngestionPipeline(db)
    assert pipe.store_item(src, _item(URL_A)) is True
    assert pipe.store_item(src, _item(URL_A)) is False
    doc = db.query(Document).one()
    assert doc.revision == 1
    db.close()


def test_ecb_like_enriched_pair_stored_as_two_distinct_documents() -> None:
    db = TestingSession()
    src = _source(db)
    pipe = NewsIngestionPipeline(db)
    meta = {IDENTITY_TEXT_KEY: ""}
    assert pipe.store_item(src, _item(URL_A, text=FULL, metadata=meta)) is True
    assert pipe.store_item(src, _item(URL_B, text=FULL, metadata=meta)) is True
    docs = db.query(Document).all()
    assert len(docs) == 2
    assert {d.content_hash for d in docs} == {
        identity_hash(TITLE, identity_url_anchor(URL_A), None),
        identity_hash(TITLE, identity_url_anchor(URL_B), None),
    }
    db.close()


def test_summary_then_full_text_keeps_single_identity() -> None:
    db = TestingSession()
    src = _source(db)
    pipe = NewsIngestionPipeline(db)
    assert pipe.store_item(src, _item(URL_A, text=SUMMARY)) is True
    enriched = _item(URL_A, text=FULL, metadata={IDENTITY_TEXT_KEY: SUMMARY})
    assert pipe.store_item(src, enriched) is False  # duplicate، نه revision
    doc = db.query(Document).one()
    assert doc.raw_text == SUMMARY and doc.revision == 1
    db.close()


def test_same_url_new_content_still_bumps_revision() -> None:
    db = TestingSession()
    src = _source(db)
    pipe = NewsIngestionPipeline(db)
    assert pipe.store_item(src, _item(URL_A, text="first body")) is True
    assert pipe.store_item(src, _item(URL_A, text="second body")) is True
    assert sorted(d.revision for d in db.query(Document).all()) == [1, 2]
    db.close()


def test_ridless_rows_keep_previous_identity_behaviour() -> None:
    db = TestingSession()
    src = _source(db)
    pipe = NewsIngestionPipeline(db)
    item = RawItem(title="cpi", url=None, raw_text=None, metadata={"external_id": "cpi:2026-01"})
    assert pipe.store_item(src, item) is True
    assert pipe.store_item(src, item) is False
    assert db.query(Document).count() == 1
    db.close()


def test_no_description_and_empty_description_are_handled_by_one_rule() -> None:
    """نبودن کلید و تهی‌بودن کلید هر دو به لنگر URL می‌رسند (قرارداد واحد)."""
    absent = normalize(RawItem(title=TITLE, url=URL_A, raw_text=None, metadata={}))
    empty = normalize(RawItem(title=TITLE, url=URL_A, raw_text=FULL,
                              metadata={IDENTITY_TEXT_KEY: ""}))
    expected = identity_hash(TITLE, None, None, URL_A)
    assert absent.content_hash == empty.content_hash == expected
    assert not (absent.raw_text or "")  # متن خام کامل جایگزین نشده
