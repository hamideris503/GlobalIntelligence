"""Analytics — توابع خالص موتور روایت (Phase 24).

قرارداد (v1, مستند و ثابت):
- پیوند دو رویداد: حداقل ۱ موجودیت مشترک (canonical نرمال‌شده) یا حداقل
  ۲ موضوع مشترک. آستانه‌ها ثابت‌اند تا خوشه‌بندی تکرارپذیر باشد.
- strength در [0, 1]:
  strength = 0.5*min(1, events/10) + 0.5*min(1, sources/5)
- confidence از تعداد رویداد: ۱→0.3، ۲–۴→0.5، ≥۵→0.7.
- عنوان: سه عبارت پربسامد (موضوع/موجودیت/نوع) + شمار رویدادها.
- واگرایی موضع = ۱ − سهم موضع غالب (تهی اگر موضعی ثبت نشده).
- بدون AI؛ فقط ریاضیات قطعی.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class NarrativeStats:
    title: str
    strength: float
    dominant_stance: str | None
    stance_divergence: float | None
    confidence: float
    method: str = "narrative_v1"


def linked(
    entities_a: frozenset[str],
    entities_b: frozenset[str],
    topics_a: frozenset[str],
    topics_b: frozenset[str],
) -> bool:
    """آیا دو رویداد به یک روایت وصل می‌شوند؟"""
    if entities_a & entities_b:
        return True
    return len(topics_a & topics_b) >= 2


def confidence_for(n: int) -> float:
    if n >= 5:
        return 0.7
    if n >= 2:
        return 0.5
    return 0.3


def strength(n_events: int, n_sources: int) -> float:
    return round(
        0.5 * min(1.0, n_events / 10.0) + 0.5 * min(1.0, n_sources / 5.0), 4
    )


def build_title(
    terms: Counter, event_types: Counter, n_events: int, max_terms: int = 3
) -> str:
    top = [t for t, _ in terms.most_common(max_terms)]
    kind = event_types.most_common(1)[0][0] if event_types else "events"
    head = " · ".join(top) if top else kind
    return f"{head} ({n_events} events)"[:512]


def stance_split(stances: list[str]) -> tuple[str | None, float | None]:
    """(موضع غالب، واگرایی)؛ بدون موضع → (None, None)."""
    valid = [s for s in stances if s]
    if not valid:
        return None, None
    top, count = Counter(valid).most_common(1)[0]
    return top, round(1.0 - count / len(valid), 4)


class UnionFind:
    """Union-Find سبک برای خوشه‌بندی رویدادها."""

    def __init__(self) -> None:
        self.parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)

    def groups(self) -> list[list[int]]:
        buckets: dict[int, list[int]] = {}
        for x in list(self.parent):
            buckets.setdefault(self.find(x), []).append(x)
        return [sorted(v) for v in buckets.values()]


__all__ = [
    "NarrativeStats",
    "UnionFind",
    "build_title",
    "confidence_for",
    "linked",
    "stance_split",
    "strength",
]
