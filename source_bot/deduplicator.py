"""Deduplicator — فقط wrapper روی سرویس موجود؛ منطق تکراری ندارد.

- دقیق: external_id معتبر / canonical URL / content_hash + قید یکتایی DB
- نزدیک: MinHash/LSH موجود با آستانه قابل تنظیم
- provenance: رکورد canonical حفظ، تکراری به خوشه لینک می‌شود، حذف فیزیکی نیست
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from domains.news.dedup import DedupInput, cluster_documents
from domains.news.normalizer import content_hash


def canonical_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        p = urlparse(url.strip())
        if p.scheme not in ("http", "https"):
            return None
        path = p.path.rstrip("/") or "/"
        query = f"?{p.query}" if p.query else ""
        return f"{p.scheme}://{(p.hostname or '').lower()}{path}{query}"
    except Exception:  # noqa: BLE001
        return None


@dataclass
class DedupDecision:
    is_duplicate: bool
    kind: str  # new | exact | near | repost
    canonical_key: str | None = None
    similarity: float = 0.0


def exact_key(external_id: str | None, canon: str | None, chash: str | None) -> str | None:
    if external_id:
        return f"ext:{external_id.strip()}"
    if canon:
        return f"url:{canon}"
    if chash:
        return f"hash:{chash}"
    return None


def near_duplicate(a_text: str | None, b_text: str | None, *, threshold: float = 0.7) -> DedupDecision:
    """مقایسه دو متن با موتور موجود. عنوان به‌تنهایی کافی نیست (متن کامل لازم است)."""
    res = cluster_documents(
        [DedupInput(id="a", text=a_text), DedupInput(id="b", text=b_text)],
        near_threshold=threshold,
    )
    same = res.cluster_of.get("a") == res.cluster_of.get("b") and "a" in res.cluster_of
    if same:
        sim = res.pairs[0].similarity if res.pairs else 1.0
        kind = res.pairs[0].kind if res.pairs else "near"
        return DedupDecision(True, kind, res.cluster_of.get("a"), sim)
    return DedupDecision(False, "new")


def content_key_for(title: str | None, body: str | None) -> str | None:
    return content_hash(title, body)
