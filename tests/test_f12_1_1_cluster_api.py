"""F12.1.1 — F-21: خوشهٔ dedup در API خبر + فیلتر خوشه در /api/dedup/clusters.

قبل از این مرحله `ArticleClassifiedRead` فیلد `duplicate_cluster` نداشت و UI مجبور بود
کل جدول خوشه‌ها را بگیرد تا خوشهٔ یک مقاله را پیدا کند.
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from tests.conftest import TestingSession


def _seed() -> dict[str, str]:
    """سه مقاله: دو در خوشهٔ cl-1، یک بدون خوشه. شناسه‌ها برگردانده می‌شوند."""
    session = TestingSession()
    try:
        src = Source(name="F12Src", domain="f12.local", type="rss", active=True)
        session.add(src)
        session.flush()
        ids: dict[str, str] = {}
        for i, cluster in enumerate(("cl-1", "cl-1", None)):
            doc = Document(
                source_id=src.id, title=f"doc{i}", raw_text="text",
                content_hash=f"f12-{i}", doc_metadata="{}",
            )
            session.add(doc)
            session.flush()
            art = Article(
                document_id=doc.id, title=f"article{i}", summary="s",
                topics='["economy"]', duplicate_cluster=cluster,
            )
            session.add(art)
            session.flush()
            ids[str(art.id)] = cluster or ""
        session.commit()
        return ids
    finally:
        session.close()


def test_classify_articles_expose_duplicate_cluster(client: TestClient) -> None:
    ids = _seed()
    rows = client.get("/api/classify/articles", params={"only_classified": False}).json()
    mine = {r["id"]: r.get("duplicate_cluster") for r in rows if r["id"] in ids}
    assert set(mine) == set(ids)
    assert mine[ids and next(k for k, v in ids.items() if v == "cl-1")] == "cl-1"
    no_cluster = next(k for k, v in ids.items() if v == "")
    assert mine[no_cluster] is None


def test_classify_article_detail_exposes_duplicate_cluster(client: TestClient) -> None:
    ids = _seed()
    clustered = next(k for k, v in ids.items() if v == "cl-1")
    body = client.get(f"/api/classify/articles/{clustered}").json()
    assert body["duplicate_cluster"] == "cl-1"

    plain = next(k for k, v in ids.items() if v == "")
    body2 = client.get(f"/api/classify/articles/{plain}").json()
    assert body2["duplicate_cluster"] is None


def test_dedup_clusters_filters_by_cluster(client: TestClient) -> None:
    ids = _seed()
    clustered = [k for k, v in ids.items() if v == "cl-1"]

    rows = client.get("/api/dedup/clusters", params={"cluster": "cl-1"}).json()
    assert {r["article_id"] for r in rows} == set(clustered)
    assert all(r["cluster"] == "cl-1" for r in rows)

    assert client.get("/api/dedup/clusters", params={"cluster": "missing"}).json() == []


def test_dedup_clusters_without_filter_keeps_old_behaviour(client: TestClient) -> None:
    ids = _seed()
    rows = client.get("/api/dedup/clusters").json()
    found = {r["article_id"] for r in rows}
    assert set(ids) <= found


def _seed_metadata_only(cluster: str, title: str) -> str:
    """مقاله‌ای که خوشه‌اش فقط در doc_metadata است (دادهٔ قدیمی)."""
    session = TestingSession()
    try:
        src = Source(name=f"F12Meta {title}", domain="f12.local", type="rss", active=True)
        session.add(src)
        session.flush()
        doc = Document(
            source_id=src.id, title=title, raw_text="text",
            content_hash=f"meta-{title}",
            doc_metadata=json.dumps({"dedup_cluster": cluster}),
        )
        session.add(doc)
        session.flush()
        art = Article(
            document_id=doc.id, title=title, summary="s",
            topics='["economy"]', duplicate_cluster=None,
        )
        session.add(art)
        session.commit()
        return str(art.id)
    finally:
        session.close()


def test_dedup_clusters_find_metadata_only_cluster(client: TestClient) -> None:
    """شکاف قبلی: فیلتر سمت سرور فقط ستون را می‌دید و دادهٔ قدیمی را پیدا نمی‌کرد."""
    target = _seed_metadata_only("cl-meta", "meta-one")
    rows = client.get("/api/dedup/clusters", params={"cluster": "cl-meta"}).json()
    assert [r["article_id"] for r in rows] == [target]
    assert rows[0]["cluster"] == "cl-meta"


def test_dedup_clusters_filter_is_exact_not_substring(client: TestClient) -> None:
    """prefilter LIKE کاندید می‌آورد؛ تطابق نهایی باید دقیق باشد."""
    target = _seed_metadata_only("cl-meta", "meta-exact")
    other = _seed_metadata_only("cl-meta-2", "meta-other")
    rows = client.get("/api/dedup/clusters", params={"cluster": "cl-meta"}).json()
    ids = [r["article_id"] for r in rows]
    assert target in ids
    assert other not in ids
