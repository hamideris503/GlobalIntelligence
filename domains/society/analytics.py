"""Analytics — توابع خالص هوش اجتماعی (Phase 23).

قرارداد (v1, مستند و ثابت):
- mood: میانگین احساس [-1, 1]؛ بدون احساس معتبر → None.
- unrest: سهم مقالات دارای حداقل یک موضوع ناآرامی؛ بدون مقاله → None.
- stance_mix: فراوانی مواضع غیرتهی (ممکن است تهی باشد، نه خطا).
- confidence از تعداد مقاله: ۱→0.3، ۲–۴→0.5، ≥۵→0.7.
- بدون AI؛ فقط ریاضیات قطعی.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MoodStats:
    avg_sentiment: float | None
    article_count: int
    unrest_share: float | None
    stance_mix: dict[str, int] = field(default_factory=dict)
    confidence: float = 0.3
    method: str = "mood_v1"


def confidence_for(n: int) -> float:
    if n >= 5:
        return 0.7
    if n >= 2:
        return 0.5
    return 0.3


def mood(
    sentiments: list[float | None],
    topic_sets: list[set[str]],
    stances: list[str | None],
    unrest_topics: frozenset[str],
) -> MoodStats | None:
    """خلاصه‌ی اجتماعی یک قلمرو؛ بدون مقاله → None."""
    n = len(topic_sets)
    if n <= 0:
        return None
    valid = [s for s in sentiments if s is not None]
    avg = round(sum(valid) / len(valid), 4) if valid else None
    hits = sum(1 for ts in topic_sets if ts & unrest_topics)
    mix = dict(Counter(s for s in stances if s))
    return MoodStats(
        avg_sentiment=avg,
        article_count=n,
        unrest_share=round(hits / n, 4),
        stance_mix=mix,
        confidence=confidence_for(n),
    )


__all__ = ["MoodStats", "confidence_for", "mood"]
