"""Tests for deduplication (Phase 9)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news.dedup import (
    DedupInput,
    cluster_documents,
    jaccard_from_signatures,
    minhash_signature,
    shingles,
)
from domains.news.dedup_service import DedupService
from tests.conftest import TestingSession


# --- unit: minhash ---
def test_shingles_and_identical_sets() -> None:
    a = shingles("the quick brown fox jumps over the lazy dog")
    b = shingles("the quick brown fox jumps over the lazy dog")
    assert a == b
    assert jaccard_from_signatures(minhash_signature(a), minhash_signature(b)) == 1.0


def test_minhash_similar_texts_high_similarity() -> None:
    a = shingles("oil prices rise on supply concerns in the market today")
    b = shingles("oil prices rise on supply concerns in the market now")
    sim = jaccard_from_signatures(minhash_signature(a), minhash_signature(b))
    assert sim > 0.5


def test_minhash_different_texts_low_similarity() -> None:
    a = shingles("oil prices rise on supply concerns")
    b = shingles("apple releases a new smartphone model")
    sim = jaccard_from_signatures(minhash_signature(a), minhash_signature(b))
    assert sim < 0.3


# --- clustering ---
def test_empty_documents_do_not_cluster() -> None:
    """اسناد بدون متن نباید به هم بچسبند (P1-7)."""
    items = [
        DedupInput(id="1", text=None, content_hash=None, source_name="A"),
        DedupInput(id="2", text="", content_hash=None, source_name="B"),
        DedupInput(id="3", text="   ", content_hash=None, source_name="C"),
    ]
    res = cluster_documents(items)
    roots = {res.cluster_id_for(i) for i in ("1", "2", "3")}
    assert len(roots) == 3  # هر کدام خوشه‌ی خودش


def test_cluster_id_is_deterministic() -> None:
    items = [
        DedupInput(id="b", text="same text here for clustering", content_hash="x"),
        DedupInput(id="a", text="same text here for clustering", content_hash="x"),
    ]
    res1 = cluster_documents(items)
    res2 = cluster_documents(list(reversed(items)))
    assert res1.cluster_id_for("a") == res2.cluster_id_for("a")
    assert res1.cluster_id_for("a") == "a"  # کمترین id = نماینده


def test_exact_duplicates_cluster() -> None:
    items = [
        DedupInput(id="1", text="hello world news", content_hash="h1"),
        DedupInput(id="2", text="different text", content_hash="h1"),
        DedupInput(id="3", text="unique content here", content_hash="h2"),
    ]
    res = cluster_documents(items)
    assert res.cluster_id_for("1") == res.cluster_id_for("2")
    assert res.cluster_id_for("1") != res.cluster_id_for("3")


def test_near_and_repost_detection() -> None:
    base = "central bank holds interest rate steady amid inflation concerns"
    items = [
        DedupInput(id="a", text=base, source_name="Source A"),
        DedupInput(id="b", text=base + " today", source_name="Source B"),
    ]
    res = cluster_documents(items, near_threshold=0.5)
    assert res.cluster_id_for("a") == res.cluster_id_for("b")
    assert any(p.kind == "repost" for p in res.pairs)


# --- service over DB ---
def _seed_docs() -> None:
    session = TestingSession()
    try:
        src = Source(name="DedupSrc", domain="x.local", type="rss", active=True)
        session.add(src)
        session.flush()
        for i, text in enumerate(
            [
                "oil prices rise on supply concerns today",
                "oil prices rise on supply concerns today",  # exact dup
                "completely unrelated story about technology",
            ]
        ):
            session.add(
                Document(
                    source_id=src.id,
                    title=f"doc{i}",
                    raw_text=text,
                    content_hash="same" if i < 2 else f"h{i}",
                    doc_metadata="{}",
                )
            )
        session.commit()
    finally:
        session.close()


def test_dedup_service_runs() -> None:
    _seed_docs()
    session = TestingSession()
    try:
        summary = DedupService(session).run(limit=100)
        assert summary["documents"] == 3
        assert summary["duplicate_clusters"] >= 1
        assert summary["exact_pairs"] >= 1
    finally:
        session.close()


def test_dedup_api(client: TestClient) -> None:
    _seed_docs()
    res = client.post("/api/dedup/run?limit=100")
    assert res.status_code == 200
    body = res.json()
    assert body["documents"] == 3
    assert body["duplicate_clusters"] >= 1
