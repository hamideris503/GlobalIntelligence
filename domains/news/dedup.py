"""Deduplication — تشخیص دقیق، نزدیک، repost و same-story (Phase 9).

پیاده‌سازی بدون وابستگی خارجی (Free-First):
- shingling + MinHash برای تخمین Jaccard
- LSH banding برای یافتن جفت‌های کاندید به‌صورت کارا
- Union-Find برای ساخت خوشه‌ها

خروجی: شناسه‌ی خوشه (cluster id) و رابطه‌ی جفت‌ها با نوع (exact/near/repost).
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field

# --- پارامترهای پیش‌فرض ---
SHINGLE_SIZE = 5          # اندازه‌ی k-gram (کلمات)
NUM_PERM = 64             # تعداد هش‌های MinHash
BANDS = 32                # تعداد باندهای LSH (recall بالاتر برای شباهت‌های متوسط)
ROWS_PER_BAND = NUM_PERM // BANDS  # 2
NEAR_DUP_THRESHOLD = 0.7  # آستانه‌ی Jaccard برای near-duplicate
MIN_TOKENS_FOR_MINHASH = 8  # اسناد کوتاه‌تر فقط exact-match می‌شوند

_MERSENNE = (1 << 61) - 1


def _tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    return [t for t in text.lower().split() if t]


def shingles(text: str | None, k: int = SHINGLE_SIZE) -> set[int]:
    """مجموعه‌ی هش k-gramها."""
    tokens = _tokenize(text)
    if len(tokens) < k:
        if not tokens:
            return set()
        return {_stable_hash(" ".join(tokens))}
    out: set[int] = set()
    for i in range(len(tokens) - k + 1):
        out.add(_stable_hash(" ".join(tokens[i : i + k])))
    return out


def _stable_hash(value: str) -> int:
    return int.from_bytes(hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest(), "big")


def _permutations(n: int = NUM_PERM) -> list[tuple[int, int]]:
    """(a, b) برای هش‌های خطی MinHash (deterministic)."""
    perms = []
    for i in range(n):
        a = _stable_hash(f"a{i}") % _MERSENNE
        b = _stable_hash(f"b{i}") % _MERSENNE
        perms.append((a or 1, b))
    return perms


_PERMS = _permutations()


def minhash_signature(shingle_set: set[int], num_perm: int = NUM_PERM) -> tuple[int, ...]:
    """امضای MinHash برای یک مجموعه‌ی shingle."""
    if not shingle_set:
        return tuple([0] * num_perm)
    sig = []
    for a, b in _PERMS[:num_perm]:
        m = min(((a * h + b) % _MERSENNE) for h in shingle_set)
        sig.append(m)
    return tuple(sig)


def jaccard_from_signatures(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    """تخمین Jaccard از دو امضای MinHash."""
    if not a or not b:
        return 0.0
    equal = sum(1 for x, y in zip(a, b, strict=False) if x == y)
    return equal / len(a)


def lsh_bands(sig: tuple[int, ...], bands: int = BANDS) -> list[tuple[int, int]]:
    """باندهای LSH برای یک امضا: لیست (band_index, band_hash)."""
    rows = len(sig) // bands
    out = []
    for b in range(bands):
        chunk = sig[b * rows : (b + 1) * rows]
        out.append((b, _stable_hash(",".join(map(str, chunk)))))
    return out


# --- Union-Find ---
class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        # path compression
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, x: str, y: str) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self.parent[ry] = rx


@dataclass
class DedupInput:
    """یک سند برای dedup."""

    id: str
    text: str | None
    content_hash: str | None = None
    source_name: str | None = None


@dataclass
class DedupPair:
    a: str
    b: str
    similarity: float
    kind: str  # exact | near | repost


@dataclass
class DedupResult:
    clusters: dict[str, list[str]] = field(default_factory=dict)  # root -> [doc ids]
    cluster_of: dict[str, str] = field(default_factory=dict)      # doc id -> cluster root
    pairs: list[DedupPair] = field(default_factory=list)

    def cluster_id_for(self, doc_id: str) -> str | None:
        return self.cluster_of.get(doc_id)


def cluster_documents(
    items: list[DedupInput],
    *,
    near_threshold: float = NEAR_DUP_THRESHOLD,
    same_source_dupes: bool = True,
) -> DedupResult:
    """اسناد را به خوشه‌های تکراری/مشابه خوشه‌بندی می‌کند."""
    result = DedupResult()
    if not items:
        return result

    uf = _UnionFind()
    for it in items:
        uf.find(it.id)

    # 1) exact: content_hash یکسان
    by_hash: dict[str, list[str]] = defaultdict(list)
    for it in items:
        if it.content_hash:
            by_hash[it.content_hash].append(it.id)
    for _, ids in by_hash.items():
        if len(ids) > 1:
            for other in ids[1:]:
                uf.union(ids[0], other)
                result.pairs.append(DedupPair(ids[0], other, 1.0, "exact"))

    # 2) near-duplicate: MinHash + LSH
    sigs: dict[str, tuple[int, ...]] = {}
    meta: dict[str, DedupInput] = {it.id: it for it in items}
    eligible: list[str] = []
    for it in items:
        tokens = _tokenize(it.text)
        if len(tokens) < MIN_TOKENS_FOR_MINHASH:
            # اسناد کوتاه/خالی وارد MinHash نمی‌شوند (P1-7)
            continue
        sigs[it.id] = minhash_signature(shingles(it.text))
        eligible.append(it.id)

    buckets: dict[tuple[int, int], list[str]] = defaultdict(list)
    for doc_id in eligible:
        for band in lsh_bands(sigs[doc_id]):
            buckets[band].append(doc_id)

    seen_pairs: set[tuple[str, str]] = set()
    for _, ids in buckets.items():
        if len(ids) < 2:
            continue
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                key = tuple(sorted((a, b)))
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                sim = jaccard_from_signatures(sigs[a], sigs[b])
                if sim >= near_threshold:
                    uf.union(a, b)
                    src_a = meta[a].source_name
                    src_b = meta[b].source_name
                    kind = "near"
                    if src_a and src_b and src_a != src_b:
                        kind = "repost"
                    result.pairs.append(DedupPair(a, b, round(sim, 4), kind))

    # 3) ساخت خوشه‌ها با شناسه‌ی قطعی (کمترین id = نماینده)
    raw_groups: dict[str, list[str]] = defaultdict(list)
    for it in items:
        raw_groups[uf.find(it.id)].append(it.id)

    for ids in raw_groups.values():
        canonical = min(ids)  # قطعی و پایدار
        for doc_id in ids:
            result.cluster_of[doc_id] = canonical
        result.clusters[canonical] = sorted(ids)

    return result
