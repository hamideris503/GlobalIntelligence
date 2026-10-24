"""تست‌های آفلاین ابزار حسابرسی خبرهای یکتا و کیفیت provenance/text_status.

فقط SQLite در حافظه؛ بدون شبکه، بدون AI و بدون نوشتن در دیتابیس اصلی.
"""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from scripts.audit_source_bot_unique_news import (
    _select_only,
    analysis_canonical,
    classify_full_text,
    collect,
    doc_needs_review,
    is_suspected_param,
    parse_url,
    provenance_missing,
    suspected_tracking_params,
    text_status_bucket,
)
from source_bot.deduplicator import canonical_url

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
LONG = "central bank kept the policy rate unchanged and signalled patience " * 4


def _collect(specs, articles=None, statements=None):
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    session = sessionmaker(bind=eng)()
    sources = {}
    for spec in specs:
        name = spec.pop("source", "src-a")
        if name not in sources:
            sources[name] = Source(name=name, domain=f"{name}.test", collection_method="rss",
                                   type="rss", feed_url=f"https://{name}.test/rss", active=True)
            session.add(sources[name])
            session.flush()
        json_meta = spec.pop("doc_metadata", None)
        session.add(Document(source_id=sources[name].id, retrieved_at=NOW,
                             doc_metadata=json_meta, **spec))
    session.commit()
    for art in articles or []:
        session.add(Article(classification_status="PENDING", classification_attempts=0, **art))
    session.commit()
    if statements is not None:
        @event.listens_for(eng, "before_cursor_execute")
        def _record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)
    with eng.connect() as conn:
        report = collect(conn)
    session.close()
    eng.dispose()
    return report


def _dq_rows(report):
    return {row["source"]: row for row in report["data_quality"]["per_source"]}


def _src_rows(report):
    return {row["source"]: row for row in report["unique_news"]["per_source"]}


# --- توابع خالص -------------------------------------------------------------------

def test_suspected_params_are_recognised_but_not_production_rule():
    assert is_suspected_param("utm_source") and is_suspected_param("at_medium")
    assert is_suspected_param("traffic_source") and is_suspected_param("fbclid")
    assert not is_suspected_param("id") and not is_suspected_param("page")
    url = "https://x.test/a?utm_source=rss&id=7"
    assert suspected_tracking_params(url) == {"utm_source": "rss"}
    # تولیدی: query حفظ می‌شود؛ تحلیلی: پارامتر مشکوک حذف می‌شود (جدا و بدون اثر روی hash)
    assert canonical_url(url) == "https://x.test/a?utm_source=rss&id=7"
    assert analysis_canonical(url) == "https://x.test/a?id=7"


def test_invalid_url_is_rejected_without_raising():
    for bad in ("not a url", "ftp://x.test/a", "", None, "   "):
        assert parse_url(bad) is None
        assert suspected_tracking_params(bad) == {}
        assert analysis_canonical(bad) is None


def test_select_guard_blocks_writes():
    assert _select_only("select 1").lstrip().upper().startswith("SELECT")
    for sql in ("update documents set content_hash='x'", "delete from documents", "insert into x"):
        with pytest.raises(RuntimeError):
            _select_only(sql)


def test_classify_contract_buckets():
    base = {"provenance": "real", "raw_text": LONG, "metadata": {}}
    assert classify_full_text({**base, "metadata": {"text_status": "rss_summary_only"}})["bucket"] \
        == "rss_summary_only"
    assert classify_full_text({**base, "metadata": {"text_status": "extraction_failed"}})["bucket"] \
        == "extraction_failed"
    by_len = classify_full_text({**base, "metadata": {"text_status": "full_text_extracted",
                                                      "identity_text": "short summary"}})
    assert by_len["bucket"] == "full_text_verified_by_length" and not by_len["needs_review"]
    by_status = classify_full_text({**base, "metadata": {"text_status": "full_text_extracted",
                                                         "identity_text": ""}})
    assert by_status["bucket"] == "full_text_verified_by_status" and by_status["needs_review"]
    not_expanded = classify_full_text({**base, "raw_text": "tiny",
                                       "metadata": {"text_status": "full_text_extracted",
                                                    "identity_text": "much longer summary"}})
    assert not_expanded["bucket"] == "full_text_not_expanded" and not_expanded["needs_review"]
    assert classify_full_text({**base, "provenance": "mock",
                               "metadata": {"text_status": "full_text_extracted"}})["bucket"] == "mock"
    assert classify_full_text({**base, "metadata": {}})["bucket"] == "text_status_missing"
    assert classify_full_text({**base, "provenance": "unknown"})["bucket"] == "unknown_provenance"
    source_provided = classify_full_text({**base, "metadata":
                                          {"text_status": "source_provided_only"}})
    assert source_provided["bucket"] == "source_provided_only"
    assert source_provided["needs_review"] is False


def test_text_status_bucket_covers_missing_and_invalid():
    assert text_status_bucket({"text_status": "full_text_extracted"}) == "full_text_extracted"
    assert text_status_bucket({"text_status": "rss_summary_only"}) == "rss_summary_only"
    assert text_status_bucket({"text_status": "source_provided_only"}) == "source_provided_only"
    assert text_status_bucket({"text_status": "extraction_failed"}) == "extraction_failed"
    assert text_status_bucket({}) == "missing"
    assert text_status_bucket({"text_status": None}) == "missing"
    assert text_status_bucket({"text_status": "   "}) == "missing"
    assert text_status_bucket(None) == "missing"
    assert text_status_bucket({"text_status": "openai"}) == "unknown"
    assert text_status_bucket({"text_status": 5}) == "unknown"
    assert provenance_missing({"provenance_missing": True}) is True
    assert provenance_missing({"provenance_missing": "true"}) is False
    assert provenance_missing({}) is False


# --- شمارش خبر یکتا ---------------------------------------------------------------

def test_identical_url_is_one_news():
    report = _collect([
        {"url": "https://a.test/x", "title": "T", "raw_text": "body", "hash": "h1",
         "content_hash": "c1", "revision": 1},
        {"url": "https://a.test/x", "title": "T", "raw_text": "body", "hash": "h1",
         "content_hash": "c2", "revision": 2},
    ])
    row = _src_rows(report)["src-a"]
    assert row["documents"] == 2 and row["distinct_raw_url"] == 1
    assert row["distinct_news_by_url_hash"] == 1
    assert row["news_with_multiple_rows"] == 1 and row["max_rows_per_news"] == 2
    assert report["unique_news"]["distinct_news_total_by_source"] == 1


def test_tracking_only_difference_is_flagged_as_suspected_duplicate():
    report = _collect([
        {"url": "https://www.bbc.co.uk/news/articles/x1?at_medium=RSS&at_campaign=rss",
         "title": "Same story", "raw_text": "same body", "hash": "h1", "content_hash": "c1"},
        {"url": "https://www.bbc.co.uk/news/articles/x1",
         "title": "Same story", "raw_text": "same body", "hash": "h2", "content_hash": "c1"},
    ])
    row = _src_rows(report)["src-a"]
    assert row["distinct_raw_url"] == 2 and row["distinct_news_by_url_hash"] == 2
    assert row["urls_with_suspected_params"] == 1
    pair = row["suspected_duplicate_pairs"][0]
    assert pair["host_and_path_equal"] is True and pair["title_equal"] is True
    assert set(pair["only_in_a"]) | set(pair["only_in_b"]) == {"at_medium", "at_campaign"}
    assert pair["identical_after_analysis_drop"] is True
    assert pair["verdict"] == "same_news_supported"
    assert report["url_params"]["hypothetical_normalization"]["would_merge_total"] == 1


def test_different_path_is_not_a_pair():
    report = _collect([
        {"url": "https://a.test/x1", "title": "A", "raw_text": "a", "hash": "h1",
         "content_hash": "c1"},
        {"url": "https://a.test/x2", "title": "A", "raw_text": "a", "hash": "h2",
         "content_hash": "c2"},
    ])
    row = _src_rows(report)["src-a"]
    assert row["suspected_duplicate_pairs"] == []
    assert row["distinct_news_by_url_hash"] == 2
    assert report["url_params"]["hypothetical_normalization"]["would_merge_total"] == 0


def test_meaningful_query_difference_is_not_treated_as_tracking():
    report = _collect([
        {"url": "https://a.test/x?id=1", "title": "T", "raw_text": "body", "hash": "h1",
         "content_hash": "c1"},
        {"url": "https://a.test/x?id=2", "title": "T", "raw_text": "body", "hash": "h2",
         "content_hash": "c1"},
    ])
    row = _src_rows(report)["src-a"]
    pair = row["suspected_duplicate_pairs"][0]
    assert pair["conflicting_values"] == {"id": {"a": "1", "b": "2"}}
    assert pair["identical_after_analysis_drop"] is False
    assert pair["suspected_params"] == []
    assert pair["verdict"] == "same_news_supported"  # عنوان/متن یکسان، ولی URL یکسان نشد
    params = {p["name"]: p for p in report["url_params"]["params"]}
    assert params["id"]["suspected_tracking"] is False


def test_invalid_url_does_not_break_counts():
    report = _collect([
        {"url": "not a url", "title": "T", "raw_text": "b", "hash": "h1", "content_hash": "c1"},
        {"url": None, "title": "T2", "raw_text": "b", "hash": None, "content_hash": "c2"},
    ])
    row = _src_rows(report)["src-a"]
    assert row["documents"] == 2 and row["distinct_raw_url"] == 2
    assert row["suspected_duplicate_pairs"] == []
    assert row["guid_signals"]["missing"] == 2
    assert report["data_quality"]["double_scheme_documents"] == 0
    assert report["data_quality"]["synthetic_documents"] == 0


def test_synthetic_and_double_scheme_urls_are_flagged():
    report = _collect([
        {"url": "https://example.local/news/2?v=2026-10-12", "title": "T", "raw_text": "b",
         "hash": "h1", "content_hash": "c1"},
        {"url": "https://https://example.local/news/2", "title": "T2", "raw_text": "b",
         "hash": "h2", "content_hash": "c2"},
    ])
    dq = report["data_quality"]
    assert dq["synthetic_documents"] == 2
    assert dq["double_scheme_documents"] == 1
    assert any(h["synthetic"] for h in dq["hosts"])


def test_same_title_different_url_is_two_news():
    report = _collect([
        {"url": "https://a.test/x1", "title": "Identical title", "raw_text": "b1", "hash": "h1",
         "content_hash": "c1"},
        {"url": "https://a.test/x2", "title": "Identical title", "raw_text": "b1", "hash": "h2",
         "content_hash": "c1"},
    ])
    row = _src_rows(report)["src-a"]
    assert row["distinct_news_by_url_hash"] == 2
    assert row["distinct_content_hash"] == 1  # هش محتوا یکی است؛ تفکیک با URL انجام می‌شود


def test_full_text_buckets_and_needs_review():
    report = _collect([
        {"url": "https://a.test/1", "title": "mock", "raw_text": LONG, "hash": "h1",
         "content_hash": "c1", "doc_metadata": '{"mock": true, "text_status": "full_text_extracted"}'},
        {"url": "https://a.test/2", "title": "sum", "raw_text": "short", "hash": "h2",
         "content_hash": "c2", "doc_metadata": '{"mock": false, "text_status": "rss_summary_only"}'},
        {"url": "https://a.test/3", "title": "full", "raw_text": LONG, "hash": "h3",
         "content_hash": "c3", "doc_metadata":
         '{"mock": false, "text_status": "full_text_extracted", "identity_text": "short"}'},
        {"url": "https://a.test/4", "title": "ecb-like", "raw_text": LONG, "hash": "h4",
         "content_hash": "c4", "doc_metadata":
         '{"mock": false, "text_status": "full_text_extracted", "identity_text": ""}'},
        {"url": "https://a.test/5", "title": "failed", "raw_text": "", "hash": "h5",
         "content_hash": "c5", "doc_metadata": '{"mock": false, "text_status": "extraction_failed"}'},
    ])
    buckets = report["full_text"]["buckets"]
    assert buckets == {"mock": 1, "rss_summary_only": 1, "full_text_verified_by_length": 1,
                       "full_text_verified_by_status": 1, "extraction_failed": 1}
    assert report["full_text"]["valid_total"] == 2
    by_src = _dq_rows(report)
    assert by_src["src-a"]["full_text_extracted"] == 3
    assert by_src["src-a"]["rss_summary_only"] == 1
    assert by_src["src-a"]["extraction_failed"] == 1
    assert by_src["src-a"]["full_text_valid"] == 2
    review = {item["id"]: item for item in report["full_text"]["needs_review"]}
    assert len(review) == 1 and next(iter(review.values()))["bucket"] \
        == "full_text_verified_by_status"


def test_incomplete_or_invalid_metadata_is_reported_not_fatal():
    report = _collect([
        {"url": "https://a.test/1", "title": "t1", "raw_text": LONG, "hash": "h1",
         "content_hash": "c1", "doc_metadata": None},
        {"url": "https://a.test/2", "title": "t2", "raw_text": LONG, "hash": "h2",
         "content_hash": "c2", "doc_metadata": "not json"},
        {"url": "https://a.test/3", "title": "t3", "raw_text": LONG, "hash": "h3",
         "content_hash": "c3", "doc_metadata":
         '{"mock": false, "text_status": "full_text_extracted", "identity_text": 5}'},
    ])
    buckets = report["full_text"]["buckets"]
    assert buckets.get("unknown_provenance") == 2
    assert buckets.get("full_text_verified_by_status") == 1
    assert len(report["full_text"]["needs_review"]) == 3
    dq = report["data_quality"]
    assert dq["provenance"]["unknown"] == 2 and dq["provenance"]["real"] == 1
    assert dq["provenance"]["mock"] == 0
    assert dq["provenance_missing"]["total"] == 0
    assert dq["text_status"]["text_status_missing"] == 2
    assert dq["text_status"]["full_text_extracted"] == 1


# --- مرحلهٔ ۳۴: دو محور مستقل provenance و text_status ------------------------------

def test_provenance_missing_overlaps_unknown_without_double_counting():
    report = _collect([
        {"url": "https://a.test/1", "title": "t1", "raw_text": "b", "hash": "h1",
         "content_hash": "c1", "doc_metadata": '{"provenance_missing": true}'},
        {"url": "https://a.test/2", "title": "t2", "raw_text": "b", "hash": "h2",
         "content_hash": "c2",
         "doc_metadata": '{"mock": false, "provenance_missing": true}'},
        {"url": "https://a.test/3", "title": "t3", "raw_text": "b", "hash": "h3",
         "content_hash": "c3", "doc_metadata": '{"mock": true}'},
    ])
    dq = report["data_quality"]
    assert (dq["provenance"]["real"], dq["provenance"]["mock"],
            dq["provenance"]["unknown"]) == (1, 1, 1)
    assert sum(dq["provenance"][k] for k in ("real", "mock", "unknown")) \
        == report["documents"]["total"] == 3
    assert dq["provenance_missing"]["total"] == 2
    assert dq["provenance_missing"]["with_unknown_provenance"] == 1
    row = _dq_rows(report)["src-a"]
    assert row["provenance_missing"] == 2 and row["unknown"] == 1 and row["real"] == 1


def test_source_provided_only_is_never_valid_full_text():
    report = _collect([
        {"url": "https://a.test/1", "title": "adapter body", "raw_text": LONG, "hash": "h1",
         "content_hash": "c1", "doc_metadata":
         '{"mock": false, "text_status": "source_provided_only", "identity_text": "x"}'},
    ])
    assert report["full_text"]["valid_total"] == 0
    assert report["full_text"]["buckets"] == {"source_provided_only": 1}
    assert report["data_quality"]["full_text_valid"] == 0
    assert report["data_quality"]["text_status"]["source_provided_only"] == 1
    assert "source_provided_only" in report["full_text"]["excluded_from_valid"]


def test_status_and_provenance_are_counted_independently():
    report = _collect([
        {"url": "https://a.test/1", "title": "mock-no-status", "raw_text": LONG, "hash": "h1",
         "content_hash": "c1", "doc_metadata": '{"mock": true}'},
        {"url": "https://a.test/2", "title": "real-summary", "raw_text": "short", "hash": "h2",
         "content_hash": "c2",
         "doc_metadata": '{"mock": false, "text_status": "rss_summary_only"}'},
        {"url": "https://a.test/3", "title": "unknown-source-provided", "raw_text": "b",
         "hash": "h3", "content_hash": "c3",
         "doc_metadata": '{"text_status": "source_provided_only"}'},
        {"url": "https://a.test/4", "title": "old", "raw_text": "b", "hash": "h4",
         "content_hash": "c4", "doc_metadata": '{"mock": false}'},
        {"url": "https://a.test/5", "title": "bad-status", "raw_text": "b", "hash": "h5",
         "content_hash": "c5", "doc_metadata":
         '{"mock": false, "text_status": "openai_classified"}'},
        {"url": "https://a.test/6", "title": "failed", "raw_text": "", "hash": "h6",
         "content_hash": "c6", "doc_metadata":
         '{"mock": false, "text_status": "extraction_failed"}'},
    ])
    ts = report["data_quality"]["text_status"]
    assert ts["text_status_missing"] == 2          # mock + old real
    assert ts["rss_summary_only"] == 1
    assert ts["source_provided_only"] == 1
    assert ts["extraction_failed"] == 1
    assert ts["text_status_unknown"] == 1
    assert sum(ts[k] for k in ("full_text_extracted", "rss_summary_only", "source_provided_only",
                               "extraction_failed", "text_status_missing",
                               "text_status_unknown")) == report["documents"]["total"]
    prov = report["data_quality"]["provenance"]
    assert (prov["real"], prov["mock"], prov["unknown"]) == (4, 1, 1)


def test_needs_review_definition():
    def verdict(prov, status, raw=LONG, anchor=None):
        doc = {"provenance": prov, "provenance_missing": False,
               "text_status_bucket": text_status_bucket({"text_status": status}),
               "raw_text": raw, "metadata": {"text_status": status, "identity_text": anchor}}
        return doc, classify_full_text(doc)

    assert doc_needs_review(*verdict("real", "rss_summary_only")) is False
    assert doc_needs_review(*verdict("real", "source_provided_only")) is False
    assert doc_needs_review(*verdict("mock", None)) is False
    assert doc_needs_review(*verdict("real", None)) is True           # واقعی بدون وضعیت
    assert doc_needs_review(*verdict("real", "openai")) is True       # وضعیت نامعتبر
    assert doc_needs_review(*verdict("unknown", "full_text_extracted", anchor="s")) is True
    assert doc_needs_review(*verdict("real", "full_text_extracted", anchor="s")) is False
    assert doc_needs_review(*verdict("real", "full_text_extracted", raw="tiny",
                                     anchor="much longer summary")) is True


def test_needs_review_total_is_reported():
    report = _collect([
        {"url": "https://a.test/1", "title": "ok", "raw_text": LONG, "hash": "h1",
         "content_hash": "c1", "doc_metadata":
         '{"mock": false, "text_status": "full_text_extracted", "identity_text": "s"}'},
        {"url": "https://a.test/2", "title": "unknown", "raw_text": LONG, "hash": "h2",
         "content_hash": "c2", "doc_metadata": "{}"},
    ])
    assert report["data_quality"]["needs_review_documents"] == 1
    assert _dq_rows(report)["src-a"]["needs_review"] == 1


def test_collect_issues_only_select_statements():
    statements = []
    report = _collect([{"url": "https://a.test/1", "title": "t", "raw_text": "b",
                        "hash": "h1", "content_hash": "c1", "doc_metadata": '{"mock": false}'}],
                      statements=statements)
    forbidden = ("INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP", "REPLACE",
                 "TRUNCATE", "GRANT", "COPY")
    writes = [s for s in statements if s.lstrip().upper().startswith(forbidden)]
    assert writes == []
    assert any(s.lstrip().upper().startswith("SELECT") for s in statements)
    assert report["documents"]["total"] == 1


def test_clusters_are_computed_in_memory_and_cross_source_detected():
    report = _collect([
        {"source": "src-a", "url": "https://a.test/1", "title": "T", "raw_text": LONG,
         "hash": "h1", "content_hash": "c1",
         "doc_metadata": '{"mock": false, "text_status": "full_text_extracted", "identity_text": "s"}'},
        {"source": "src-b", "url": "https://b.test/1", "title": "T", "raw_text": LONG,
         "hash": "h2", "content_hash": "c1",
         "doc_metadata": '{"mock": false, "text_status": "full_text_extracted", "identity_text": "s"}'},
        {"source": "src-b", "url": "https://b.test/2", "title": "Other",
         "raw_text": "completely different text about markets and inflation expectations " * 3,
         "hash": "h3", "content_hash": "c3",
         "doc_metadata": '{"mock": false, "text_status": "full_text_extracted", "identity_text": "s"}'},
    ])
    clusters = report["clusters"]
    assert clusters["eligible_full_text"] == 3 and clusters["clustered"] == 3
    assert clusters["clusters"] == 2
    assert clusters["multi_document_clusters"] == 1 and clusters["cross_source_clusters"] == 1
    assert clusters["validity"] == "not_verified_production_path_absent"
    assert clusters["stored_with_duplicate_cluster"] == 0


def test_stored_duplicate_cluster_makes_validity_computed():
    report = _collect(
        [{"url": "https://a.test/1", "title": "T", "raw_text": LONG, "hash": "h1",
          "content_hash": "c1",
          "doc_metadata": '{"mock": false, "text_status": "full_text_extracted", "identity_text": "s"}'}],
        articles=[{"title": "T", "duplicate_cluster": "cl-1"}],
    )
    assert report["clusters"]["stored_articles"] == 1
    assert report["clusters"]["stored_with_duplicate_cluster"] == 1
    assert report["clusters"]["validity"] != "not_verified_production_path_absent"
