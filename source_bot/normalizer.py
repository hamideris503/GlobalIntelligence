"""Normalizer wrapper — از normalizer موجود پروژه استفاده می‌کند؛ تکراری نمی‌سازد."""
from __future__ import annotations

from domains.news.fetchers import RawItem
from domains.news.normalizer import NormalizedItem, normalize


def normalize_item(item: RawItem) -> NormalizedItem:
    return normalize(item)
