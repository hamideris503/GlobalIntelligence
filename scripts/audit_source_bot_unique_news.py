"""حسابرسی فقط-خواندنی هویت خبر، شمارش خبرهای یکتا و کیفیت provenance/text_status.

    python -m scripts.audit_source_bot_unique_news --database globalintelligence --json out.json

قواعد:
- فقط SELECT. اتصال با `default_transaction_read_only=on` ساخته می‌شود و با
  `SHOW transaction_read_only` تأیید می‌شود؛ در غیر این صورت ابزار با exit 2 متوقف می‌شود.
- هیچ نوشتنی در دیتابیس، هیچ درخواست شبکه و هیچ فراخوانی AI انجام نمی‌شود.
- خوشه‌بندی فقط در حافظه (domains.news.dedup) محاسبه و ذخیره نمی‌شود.
- هویت از توابع تولیدی پروژه می‌آید: ستون `hash` (هش URL خام)، ستون `content_hash`
  (identity_hash) و `source_bot.deduplicator.canonical_url`.
- تحلیل «حذف پارامتر رهگیری» عمداً جدا و فقط-تحلیلی است و هرگز برای hash/ایندکس نیست.
- provenance و text_status دو محور مستقل گزارش‌اند و با هم جمع نمی‌شوند؛
  `provenance_missing` فلگ metadata است و با `unknown` هم‌پوشانی دارد.

سه عدد جدا گزارش می‌شود: اسناد، خبرهای یکتا در هر منبع، خوشه‌های مستقل سامانه‌ای.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

sys.path.insert(0, ".")

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from backend.core.config import get_settings
from backend.database.models.document import provenance_of
from domains.news.dedup import DedupInput, cluster_documents
from domains.news.fetchers import (
    EXTRACTION_FAILED,
    FULL_TEXT,
    RSS_SUMMARY_ONLY,
    SOURCE_PROVIDED_ONLY,
    TEXT_STATUS,
)
from source_bot.deduplicator import canonical_url

IDENTITY_TEXT_KEY = "identity_text"
PROVENANCE_MISSING_KEY = "provenance_missing"
# سبد وضعیت متن: از ثابت‌های تولیدی می‌آید؛ دو سبد فقط برای «نبود/نامعتبر» است.
STATUS_MISSING = "missing"
STATUS_UNKNOWN = "unknown"
TEXT_STATUS_BUCKETS = (FULL_TEXT, RSS_SUMMARY_ONLY, SOURCE_PROVIDED_ONLY,
                       EXTRACTION_FAILED, STATUS_MISSING, STATUS_UNKNOWN)
# کلید هر سبد در جدول‌ها (بدون تداخل با شمار provenance).
STATUS_ROW_KEY = {
    FULL_TEXT: "full_text_extracted",
    RSS_SUMMARY_ONLY: "rss_summary_only",
    SOURCE_PROVIDED_ONLY: "source_provided_only",
    EXTRACTION_FAILED: "extraction_failed",
    STATUS_MISSING: "text_status_missing",
    STATUS_UNKNOWN: "text_status_unknown",
}
# full-text معتبر = همان قرارداد مرحلهٔ ۳۱؛ source_provided_only هرگز اینجا نیست.
VALID_FULL_TEXT_BUCKETS = frozenset({"full_text_verified_by_length",
                                     "full_text_verified_by_status"})

# نام پارامترهایی که در عمل رهگیری‌اند. فقط برای تحلیل؛ هرگز برای hash/ایندکس.
SUSPECTED_PARAMS = frozenset({
    "at_campaign", "at_medium", "at_custom1", "at_custom2", "at_custom3", "at_custom4",
    "traffic_source", "fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid",
    "igshid", "ref_src", "spm", "yclid",
})
SUSPECTED_PREFIXES = ("utm_",)
SYSTEM_DATABASES = frozenset({"postgres", "template0", "template1"})
# ?????????? ??????/???????? ??? ???? ??????????? ????? ????? ?? ??? ?? ?????.
SYNTHETIC_HOSTS = frozenset({"example.local", "example.com", "example.org", "localhost",
                             "test.local", "127.0.0.1"})
DB_NAME_RE = re.compile(r"[A-Za-z0-9_]+")


def _select_only(sql: str) -> str:
    """هر پرس‌وجو پیش از اجرا باید SELECT باشد (گارد نوشتن)."""
    if not sql.lstrip().upper().startswith("SELECT"):
        raise RuntimeError(f"non-SELECT statement blocked: {sql[:40]}")
    return sql


def is_suspected_param(name: str) -> bool:
    low = (name or "").lower()
    return low in SUSPECTED_PARAMS or low.startswith(SUSPECTED_PREFIXES)


def parse_url(url: str | None) -> dict | None:
    """host/path/query یک URL را برمی‌گرداند؛ URL نامعتبر → None."""
    if not isinstance(url, str) or not url.strip():
        return None
    try:
        parts = urlsplit(url.strip())
        query = parse_qsl(parts.query, keep_blank_values=True)
    except Exception:  # noqa: BLE001 - URL خراب نباید حسابرسی را بشکند
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    return {"host": parts.hostname.lower(), "path": parts.path, "query": query}


def double_scheme(url: str | None) -> bool:
    """URL???? ??? `https://https://host/...` ?? ?? ?????????? ?? ??? scheme ?????."""
    if not isinstance(url, str):
        return False
    rest = re.sub(r"^[A-Za-z][A-Za-z0-9+.-]*://", "", url.strip())
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", rest))


def host_of(url: str | None) -> str | None:
    """?????? ?????? scheme??? ?????? (`https://https://host`) ???????? ??? ???????."""
    if not isinstance(url, str):
        return None
    rest = url.strip()
    while True:
        match = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", rest)
        if not match:
            break
        rest = rest[match.end():]
    host = rest.split("/")[0].split("?")[0].split("#")[0].strip().lower()
    return host or None


def suspected_tracking_params(url: str | None) -> dict[str, str]:
    parts = parse_url(url)
    if not parts:
        return {}
    return {k: v for k, v in parts["query"] if is_suspected_param(k)}


def analysis_canonical(url: str | None) -> str | None:
    """تحلیلی و جدا از تولید: `canonical_url` + حذف پارامترهای مشکوک رهگیری.

    این مقدار **فقط** برای «اثر فرضی نرمال‌سازی» گزارش می‌شود و در هیچ
    hash، ایندکس یا تصمیم dedup استفاده نمی‌شود.
    """
    base = canonical_url(url)
    if not base:
        return None
    parts = urlsplit(base)
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not is_suspected_param(k)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), ""))


def _metadata(doc_metadata: str | None) -> dict:
    if not isinstance(doc_metadata, str) or not doc_metadata.strip():
        return {}
    try:
        data = json.loads(doc_metadata)
    except Exception:  # noqa: BLE001 - metadata خراب = دادهٔ ناقص، نه کرش
        return {}
    return data if isinstance(data, dict) else {}


def provenance_missing(metadata: dict) -> bool:
    """فلگ صریح مرز ذخیره‌سازی؛ فقط JSON true معتبر است (نه "true" یا 1)."""
    return (metadata or {}).get(PROVENANCE_MISSING_KEY) is True


def text_status_bucket(metadata: dict) -> str:
    """وضعیت متن هر سند، مستقل از provenance؛ شش سبد صریح.

    کلید غایب/None/رشتهٔ خالی = missing (شکست extraction نیست)؛ مقدار ناشناخته = unknown.
    """
    meta = metadata if isinstance(metadata, dict) else {}
    status = meta.get(TEXT_STATUS)
    if TEXT_STATUS not in meta or status is None:
        return STATUS_MISSING
    if isinstance(status, str) and not status.strip():
        return STATUS_MISSING
    if isinstance(status, str) and status in (FULL_TEXT, RSS_SUMMARY_ONLY,
                                              SOURCE_PROVIDED_ONLY, EXTRACTION_FAILED):
        return status
    return STATUS_UNKNOWN


def classify_full_text(doc: dict) -> dict:
    """دسته‌بندی بر اساس قرارداد واقعی کد (provenance + text_status + مقایسهٔ متن)."""
    provenance = doc["provenance"]
    if provenance == "mock":
        return {"bucket": "mock", "needs_review": False, "reason": "provenance=mock"}
    if provenance == "unknown":
        return {"bucket": "unknown_provenance", "needs_review": True,
                "reason": "mock flag missing/invalid in doc_metadata"}
    status = text_status_bucket(doc["metadata"])
    if status == RSS_SUMMARY_ONLY:
        return {"bucket": "rss_summary_only", "needs_review": False, "reason": "text_status"}
    if status == EXTRACTION_FAILED:
        return {"bucket": "extraction_failed", "needs_review": False, "reason": "text_status"}
    if status == SOURCE_PROVIDED_ONLY:
        return {"bucket": "source_provided_only", "needs_review": False,
                "reason": "adapter text, not article extraction; never valid full text"}
    if status == STATUS_MISSING:
        return {"bucket": "text_status_missing", "needs_review": True,
                "reason": "text_status absent (not extraction failure)"}
    if status == STATUS_UNKNOWN:
        return {"bucket": "unknown_status", "needs_review": True,
                "reason": f"text_status={doc['metadata'].get(TEXT_STATUS)!r}"}
    anchor = doc["metadata"].get(IDENTITY_TEXT_KEY)
    raw_len = len(doc["raw_text"].strip())
    if isinstance(anchor, str) and anchor.strip():
        if raw_len > len(anchor.strip()):
            return {"bucket": "full_text_verified_by_length", "needs_review": False,
                    "reason": f"raw={raw_len} > summary={len(anchor.strip())}"}
        return {"bucket": "full_text_not_expanded", "needs_review": True,
                "reason": f"raw={raw_len} <= summary={len(anchor.strip())}"}
    if isinstance(anchor, str):
        return {"bucket": "full_text_verified_by_status", "needs_review": True,
                "reason": "no summary to compare; evidence = text_status + provenance + stored text"}
    return {"bucket": "full_text_verified_by_status", "needs_review": True,
            "reason": "identity_text missing; evidence = text_status + provenance"}


def doc_needs_review(doc: dict, verdict: dict) -> bool:
    """نیاز به بررسی: منشأ نامعلوم/فلگ‌دار، وضعیت نامعتبر، یا واقعی بدون وضعیت متن."""
    if doc["provenance_missing"] or doc["provenance"] == "unknown":
        return True
    if doc["text_status_bucket"] == STATUS_UNKNOWN:
        return True
    if doc["provenance"] == "real" and doc["text_status_bucket"] == STATUS_MISSING:
        return True
    return bool(verdict["needs_review"])


def _quality_per_source(docs: list[dict], verdicts: dict[str, dict]) -> list[dict]:
    """جدول کیفیت داده به تفکیک منبع: provenance و text_status دو محور مستقل‌اند."""
    rows: dict[str, dict] = {}
    for doc in docs:
        row = rows.setdefault(doc["source_name"], {
            "source": doc["source_name"], "documents": 0,
            "real": 0, "mock": 0, "unknown": 0, "provenance_missing": 0,
            "full_text_valid": 0,
            **{key: 0 for key in STATUS_ROW_KEY.values()},
            "needs_review": 0,
        })
        row["documents"] += 1
        row[doc["provenance"]] = row.get(doc["provenance"], 0) + 1
        if doc["provenance_missing"]:
            row["provenance_missing"] += 1
        row[STATUS_ROW_KEY[doc["text_status_bucket"]]] += 1
        verdict = verdicts[doc["id"]]
        if verdict["bucket"] in VALID_FULL_TEXT_BUCKETS:
            row["full_text_valid"] += 1
        if doc_needs_review(doc, verdict):
            row["needs_review"] += 1
    return [rows[key] for key in sorted(rows)]


def _iso(value) -> str | None:
    """?????? ?? PostgreSQL (datetime) ? SQLite (????)."""
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _doc(row) -> dict:
    r = row._mapping  # ?????? ?? PostgreSQL ? SQLite (RowMapping)
    meta = _metadata(r["doc_metadata"])
    return {
        "id": str(r["id"]),
        "source_id": str(r["source_id"]),
        "url": r["url"],
        "title": r["title"],
        "hash": r["hash"],
        "content_hash": r["content_hash"],
        "revision": r["revision"],
        "retrieved_at": _iso(r["retrieved_at"]),
        "raw_text": r["raw_text"] or "",
        "metadata": meta,
        "provenance": provenance_of(r["doc_metadata"]),
        "provenance_missing": provenance_missing(meta),
        "text_status_bucket": text_status_bucket(meta),
        "guid": meta.get("guid"),
    }


def _news_key(doc: dict) -> tuple[str, str]:
    """کلید خبر یکتا در منبع: هش URL؛ ردیف بدون URL با content_hash."""
    if doc["hash"]:
        return ("url", doc["hash"])
    return ("content", doc["content_hash"] or doc["id"])


def _url_pairs(docs: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = {}
    for doc in docs:
        parts = parse_url(doc["url"])
        if parts:
            groups.setdefault((parts["host"], parts["path"]), []).append(doc)
    pairs = []
    for (host, path), items in groups.items():
        urls = sorted({d["url"] for d in items})
        if len(urls) < 2:
            continue
        for i in range(len(urls)):
            for j in range(i + 1, len(urls)):
                a = next(d for d in items if d["url"] == urls[i])
                b = next(d for d in items if d["url"] == urls[j])
                qa = dict(parse_url(urls[i])["query"])
                qb = dict(parse_url(urls[j])["query"])
                only_a = {k: v for k, v in qa.items() if k not in qb}
                only_b = {k: v for k, v in qb.items() if k not in qa}
                conflicting = {k: {"a": qa[k], "b": qb[k]} for k in qa if k in qb and qa[k] != qb[k]}
                same_after_drop = analysis_canonical(urls[i]) == analysis_canonical(urls[j])
                title_equal = (a["title"] or "").strip() == (b["title"] or "").strip()
                text_equal = " ".join(a["raw_text"].split()) == " ".join(b["raw_text"].split())
                if title_equal and text_equal:
                    verdict = "same_news_supported"
                elif same_after_drop and title_equal:
                    verdict = "same_news_possible"
                else:
                    verdict = "insufficient_evidence"
                pairs.append({
                    "source": a["source_name"], "host": host, "path": path,
                    "a": {"id": a["id"], "url": urls[i]}, "b": {"id": b["id"], "url": urls[j]},
                    "host_and_path_equal": True,
                    "only_in_a": only_a, "only_in_b": only_b, "conflicting_values": conflicting,
                    "identical_after_analysis_drop": same_after_drop,
                    "suspected_params": sorted(set(only_a) | set(only_b)),
                    "title_equal": title_equal, "text_equal": text_equal,
                    "verdict": verdict,
                })
        if len(pairs) > 50:
            break
    return pairs


def guid_signal(doc: dict) -> str:
    """?????? guid ??? ?? URL ?????: match | tracking_only | different | missing."""
    guid = doc.get("guid")
    if not isinstance(guid, str) or not guid.strip():
        return "missing"
    if canonical_url(guid) == canonical_url(doc["url"]):
        return "match"
    if analysis_canonical(guid) == analysis_canonical(doc["url"]):
        return "tracking_only"
    return "different"


def _per_source(docs: list[dict]) -> list[dict]:
    out = []
    by_source: dict[str, list[dict]] = {}
    for doc in docs:
        by_source.setdefault(doc["source_id"], []).append(doc)
    for source_id, items in sorted(by_source.items(), key=lambda kv: kv[1][0]["source_name"]):
        groups: dict[tuple[str, str], int] = {}
        for doc in items:
            groups[_news_key(doc)] = groups.get(_news_key(doc), 0) + 1
        out.append({
            "source_id": source_id,
            "source": items[0]["source_name"],
            "documents": len(items),
            "distinct_raw_url": len({d["url"] for d in items}),
            "distinct_canonical_url": len({canonical_url(d["url"]) or d["url"] for d in items}),
            "distinct_content_hash": len({d["content_hash"] for d in items}),
            "distinct_news_by_url_hash": len(groups),
            "news_with_multiple_rows": sum(1 for n in groups.values() if n > 1),
            "max_rows_per_news": max(groups.values()) if groups else 0,
            "urls_with_suspected_params": sum(1 for d in items if suspected_tracking_params(d["url"])),
            "guid_signals": {
                key: sum(1 for d in items if guid_signal(d) == key)
                for key in ("match", "tracking_only", "different", "missing")
            },
            "suspected_duplicate_pairs": _url_pairs(items),
        })
    return out


def _param_census(docs: list[dict]) -> list[dict]:
    counts: dict[str, dict] = {}
    for doc in docs:
        parts = parse_url(doc["url"])
        if not parts:
            continue
        for name, value in parts["query"]:
            entry = counts.setdefault(name, {"name": name, "occurrences": 0, "sources": set(),
                                             "values": set(), "suspected_tracking": is_suspected_param(name)})
            entry["occurrences"] += 1
            entry["sources"].add(doc["source_name"])
            entry["values"].add(value)
    return [{**e, "sources": sorted(e["sources"]), "values": sorted(e["values"])[:5]}
            for e in sorted(counts.values(), key=lambda e: (-e["occurrences"], e["name"]))]


def _hypothetical(docs: list[dict]) -> dict:
    by_source: dict[str, dict] = {}
    for doc in docs:
        acc = by_source.setdefault(doc["source_id"], {"source": doc["source_name"],
                                                      "raw": set(), "analysis": set()})
        acc["raw"].add(doc["url"])
        acc["analysis"].add(analysis_canonical(doc["url"]) or doc["url"])
    rows = []
    for acc in by_source.values():
        rows.append({"source": acc["source"], "distinct_raw_url": len(acc["raw"]),
                     "distinct_after_analysis_drop": len(acc["analysis"]),
                     "would_merge": len(acc["raw"]) - len(acc["analysis"])})
    return {"per_source": rows,
            "would_merge_total": sum(r["would_merge"] for r in rows),
            "note": "تحلیلی: هیچ hash/ایندکسی تغییر نمی‌کند"}


def _clusters(docs: list[dict], articles: dict, limit: int) -> dict:
    eligible = [d for d in docs if d["provenance"] == "real"
                and d["metadata"].get(TEXT_STATUS) == FULL_TEXT]
    eligible.sort(key=lambda d: (d["retrieved_at"] or "", d["id"]), reverse=True)
    sample = eligible[:limit]
    items = [DedupInput(id=d["id"], text=d["raw_text"], content_hash=d["content_hash"],
                        source_name=d["source_name"]) for d in sample]
    result = cluster_documents(items)
    multi = {k: v for k, v in result.clusters.items() if len(v) > 1}
    src_of = {d["id"]: d["source_name"] for d in sample}
    cross = {k: v for k, v in multi.items() if len({src_of[i] for i in v}) > 1}
    if articles["with_cluster"] == 0:
        validity = "not_verified_production_path_absent"
    elif len(eligible) < 2:
        validity = "insufficient_data"
    elif len(sample) < len(eligible):
        validity = "sample_only"
    else:
        validity = "computed_offline"
    return {
        "eligible_full_text": len(eligible), "clustered": len(sample),
        "clusters": len(result.clusters), "multi_document_clusters": len(multi),
        "cross_source_clusters": len(cross), "pairs": len(result.pairs),
        "stored_articles": articles["articles"],
        "stored_with_duplicate_cluster": articles["with_cluster"],
        "validity": validity,
        "multi_clusters": [{"cluster": k, "docs": v} for k, v in list(multi.items())[:20]],
        "note": ("خوشه‌ها فقط در حافظه محاسبه شده‌اند و ذخیره نشده‌اند؛ "
                 "Article.duplicate_cluster برای اعتبارسنجی تولیدی خالی است."
                 if articles["with_cluster"] == 0 else "محاسبهٔ آفلاین"),
    }


def collect(conn, *, cluster_limit: int = 300) -> dict:
    """همهٔ سنجه‌ها را فقط با SELECT جمع می‌کند (conn می‌تواند SQLite تست باشد)."""
    sources = [dict(r._mapping) for r in conn.execute(text(_select_only(
        "select id, name, active from sources")))]
    source_names = {str(s["id"]): s["name"] for s in sources}
    docs = []
    for row in conn.execute(text(_select_only(
            "select id, source_id, url, title, raw_text, raw_payload, doc_metadata, hash, "
            "content_hash, revision, retrieved_at from documents"))):
        doc = _doc(row)
        doc["source_name"] = source_names.get(doc["source_id"], doc["source_id"])
        docs.append(doc)
    articles_total = conn.execute(text(_select_only("select count(*) from articles"))).scalar() or 0
    with_cluster = conn.execute(text(_select_only(
        "select count(duplicate_cluster) from articles"))).scalar() or 0

    classifications = {}
    for doc in docs:
        cls = classify_full_text(doc)
        classifications[doc["id"]] = cls
        doc["text_bucket"] = cls["bucket"]
    buckets: dict[str, int] = {}
    for cls in classifications.values():
        buckets[cls["bucket"]] = buckets.get(cls["bucket"], 0) + 1
    references = sorted(
        ({"id": d["id"], "source": d["source_name"],
          "bucket": classifications[d["id"]]["bucket"],
          "reason": classifications[d["id"]]["reason"]}
         for d in docs if classifications[d["id"]]["needs_review"]),
        key=lambda item: (item["source"], item["id"]),
    )
    full_text_ids = {d["id"] for d in docs if d["text_bucket"] in VALID_FULL_TEXT_BUCKETS}
    status_counts = {key: 0 for key in STATUS_ROW_KEY.values()}
    provenance: dict[str, int] = {}
    provenance_missing_total = 0
    provenance_missing_unknown = 0
    review_total = 0
    for doc in docs:
        provenance[doc["provenance"]] = provenance.get(doc["provenance"], 0) + 1
        status_counts[STATUS_ROW_KEY[doc["text_status_bucket"]]] += 1
        if doc["provenance_missing"]:
            provenance_missing_total += 1
            if doc["provenance"] == "unknown":
                provenance_missing_unknown += 1
        if doc_needs_review(doc, classifications[doc["id"]]):
            review_total += 1

    per_source = _per_source(docs)
    hosts: dict[str | None, int] = {}
    for doc in docs:
        host = host_of(doc["url"])
        hosts[host] = hosts.get(host, 0) + 1
    host_rows = [{"host": host, "documents": count,
                  "synthetic": host in SYNTHETIC_HOSTS}
                 for host, count in sorted(hosts.items(), key=lambda kv: (-kv[1], str(kv[0])))[:10]]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "documents": {
            "total": len(docs),
            "sources_total": len(sources),
            "sources_with_documents": len(per_source),
            "per_source": [{"source_id": p["source_id"], "source": p["source"],
                            "documents": p["documents"]} for p in per_source],
        },
        "data_quality": {
            "provenance": {key: provenance.get(key, 0) for key in ("real", "mock", "unknown")},
            "provenance_missing": {
                "total": provenance_missing_total,
                "with_unknown_provenance": provenance_missing_unknown,
            },
            "text_status": status_counts,
            "notes": {
                "provenance": "فقط provenance_of؛ نبود فلگ mock = unknown و URL واقعی مدرک "
                              "real بودن نیست",
                "provenance_missing": "فلگ metadata مستقل از سه دستهٔ provenance است؛ با unknown "
                                      "هم‌پوشانی دارد و نباید با آن جمع شود",
                "text_status": "شش سبد مستقل از provenance؛ missing = نبود وضعیت، نه شکست "
                               "extraction؛ source_provided_only هرگز full-text معتبر نیست",
            },
            "full_text_valid": len(full_text_ids),
            "needs_review_documents": review_total,
            "per_source": _quality_per_source(docs, classifications),
            "hosts": host_rows,
            "synthetic_documents": sum(1 for d in docs if host_of(d["url"]) in SYNTHETIC_HOSTS),
            "double_scheme_documents": sum(1 for d in docs if double_scheme(d["url"])),
        },
        "unique_news": {
            "contract": "(source_id, hash) = خبر یکتا؛ hash=sha256(URL خام)؛ "
                        "revision با همان hash ردیف دوم می‌سازد و خبر را دو بار نمی‌شمارد",
            "per_source": per_source,
            "distinct_news_total_by_source": sum(p["distinct_news_by_url_hash"] for p in per_source),
            "documents_total": len(docs),
        },
        "full_text": {
            "valid_total": len(full_text_ids),
            "buckets": buckets,
            "needs_review": references,
            "contract": "provenance=real + text_status=full_text_extracted + "
                        "(raw_text > identity_text اگر خلاصه موجود است)",
            "excluded_from_valid": [RSS_SUMMARY_ONLY, SOURCE_PROVIDED_ONLY, EXTRACTION_FAILED,
                                    STATUS_MISSING, STATUS_UNKNOWN],
            "per_source_location": "data_quality.per_source",
        },
        "url_params": {
            "params": _param_census(docs),
            "suspected_tracking": [{"id": d["id"], "source": d["source_name"], "url": d["url"],
                                    "params": suspected_tracking_params(d["url"])}
                                   for d in docs if suspected_tracking_params(d["url"])],
            "hypothetical_normalization": _hypothetical(docs),
        },
        "clusters": _clusters(docs, {"articles": int(articles_total),
                                     "with_cluster": int(with_cluster)}, cluster_limit),
    }


def render_summary(report: dict) -> str:
    lines = []
    docs = report["documents"]
    lines.append(f"database = {report.get('database')} | read_only = {report.get('read_only')} "
                 f"| generated_at = {report['generated_at']}")
    lines.append(f"A) documents: {docs['total']} in {docs['sources_with_documents']} sources "
                 f"(of {docs['sources_total']} sources)")
    for row in docs["per_source"]:
        lines.append(f"   {row['source'][:30]:30} docs={row['documents']}")
    dq = report["data_quality"]
    prov = dq["provenance"]
    lines.append(f"data quality: real={prov.get('real', 0)} mock={prov.get('mock', 0)} "
                 f"unknown={prov.get('unknown', 0)} | provenance_missing="
                 f"{dq['provenance_missing']['total']} "
                 f"(overlap_with_unknown={dq['provenance_missing']['with_unknown_provenance']}) "
                 f"synthetic={dq['synthetic_documents']} "
                 f"double_scheme={dq['double_scheme_documents']}")
    ts = dq["text_status"]
    lines.append("   text_status: " + " ".join(
        f"{key}={ts[key]}" for key in STATUS_ROW_KEY.values()) +
                 f" | valid_full_text={dq['full_text_valid']} "
                 f"needs_review={dq['needs_review_documents']}")
    lines.append("   per source: docs | real/mock/unknown | prov_missing | valid | "
                 "summary/source_provided/failed/status_missing/status_unknown | review")
    for row in dq["per_source"]:
        lines.append(
            f"   {row['source'][:26]:26} {row['documents']:4} | "
            f"{row['real']}/{row['mock']}/{row['unknown']} | {row['provenance_missing']:3} | "
            f"{row['full_text_valid']:3} | {row['rss_summary_only']}/"
            f"{row['source_provided_only']}/{row['extraction_failed']}/"
            f"{row['text_status_missing']}/{row['text_status_unknown']} | "
            f"{row['needs_review']:3}")
    lines.append("   hosts: " + ", ".join(f"{h['host']}={h['documents']}"
                                          f"{'*' if h['synthetic'] else ''}" for h in dq["hosts"]))
    lines.append("   note: provenance و text_status دو محور مستقل‌اند؛ جمع نشوند")
    lines.append("B) unique news per source (contract: source_id + url-hash)")
    for row in report["unique_news"]["per_source"]:
        lines.append(
            f"   {row['source'][:26]:26} docs={row['documents']:4} raw_url={row['distinct_raw_url']:4} "
            f"canonical={row['distinct_canonical_url']:4} content_hash={row['distinct_content_hash']:4} "
            f"news={row['distinct_news_by_url_hash']:4} multi_row_news={row['news_with_multiple_rows']} "
            f"suspect_params={row['urls_with_suspected_params']} "
            f"guid_tracking_only={row['guid_signals']['tracking_only']} "
            f"guid_different={row['guid_signals']['different']} "
            f"guid_missing={row['guid_signals']['missing']}")
        for pair in row["suspected_duplicate_pairs"]:
            lines.append(f"      pair {pair['a']['id'][:8]}~{pair['b']['id'][:8]} "
                         f"verdict={pair['verdict']} params={pair['suspected_params']} "
                         f"after_drop_equal={pair['identical_after_analysis_drop']}")
    lines.append(f"   distinct news total (by source) = "
                 f"{report['unique_news']['distinct_news_total_by_source']} "
                 f"vs documents = {docs['total']}")
    ft = report["full_text"]
    lines.append(f"full-text: valid={ft['valid_total']} (contract: {ft['contract']}) " +
                 " ".join(f"{k}={v}" for k, v in sorted(ft["buckets"].items())))
    for item in ft["needs_review"]:
        lines.append(f"   review {item['id'][:8]} {item['source'][:20]:20} "
                     f"{item['bucket']}: {item['reason']}")
    params = report["url_params"]["params"]
    lines.append("url params: " + (", ".join(
        f"{p['name']}={p['occurrences']}{'*' if p['suspected_tracking'] else ''}" for p in params)
        or "none"))
    hypo = report["url_params"]["hypothetical_normalization"]
    lines.append(f"   hypothetical drop: raw_urls={sum(r['distinct_raw_url'] for r in hypo['per_source'])} "
                 f"-> distinct={sum(r['distinct_after_analysis_drop'] for r in hypo['per_source'])} "
                 f"(would_merge={hypo['would_merge_total']}; analysis only)")
    cl = report["clusters"]
    lines.append(f"C) clusters: clustered={cl['clustered']}/{cl['eligible_full_text']} "
                 f"clusters={cl['clusters']} multi={cl['multi_document_clusters']} "
                 f"cross_source={cl['cross_source_clusters']} validity={cl['validity']} "
                 f"stored_cluster_values={cl['stored_with_duplicate_cluster']}")
    lines.append(f"   note: {cl['note']}")
    return "\n".join(lines)


def _fail(message: str) -> int:
    print(f"ABORT: {message}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only unique-news audit")
    parser.add_argument("--database", required=True, help="نام دیتابیس هدف (فقط SELECT)")
    parser.add_argument("--host", help="پیش‌فرض از DATABASE_URL")
    parser.add_argument("--port", type=int, help="پیش‌فرض از DATABASE_URL")
    parser.add_argument("--json", dest="json_path", help="مسیر نوشتن گزارش JSON")
    parser.add_argument("--cluster-limit", type=int, default=300,
                        help="حداکثر سند برای خوشه‌بندی در حافظه (پیش‌فرض 300)")
    args = parser.parse_args(argv)
    if not DB_NAME_RE.fullmatch(args.database):
        return _fail(f"invalid database name: {args.database!r}")
    if args.database in SYSTEM_DATABASES:
        return _fail(f"refusing system database: {args.database}")

    base = make_url(get_settings().database_url)
    target = base.set(database=args.database, host=args.host or base.host,
                      port=args.port or base.port)
    engine = create_engine(target, pool_pre_ping=True,
                           connect_args={"options": "-c default_transaction_read_only=on"})
    try:
        with engine.connect() as conn:
            name = conn.execute(text("select current_database()")).scalar()
            read_only = str(conn.execute(text("show transaction_read_only")).scalar()).lower()
            if name != args.database:
                return _fail(f"current_database={name!r} != requested {args.database!r}")
            if read_only != "on":
                return _fail(f"connection is not read-only (transaction_read_only={read_only})")
            report = collect(conn, cluster_limit=args.cluster_limit)
    except Exception as exc:  # noqa: BLE001 - بدون نوشتن، فقط گزارش خطا
        return _fail(f"{type(exc).__name__}: {exc}")
    finally:
        engine.dispose()

    report["database"] = name
    report["read_only"] = read_only
    report["identity_contract"] = {
        "document_hash": "sha256(raw url) — ستون hash",
        "content_hash": "identity_hash(title, identity_body(raw_text, doc_metadata), raw_payload)",
        "canonical_url": "source_bot.deduplicator.canonical_url (query حفظ می‌شود)",
        "unique_index": "uq_document_source_url_content (source_id, hash, content_hash)",
    }
    print(render_summary(report))
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"json written: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
