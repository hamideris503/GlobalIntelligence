"""Analytics — توابع خالص تحلیل ژئوپلیتیک (Phase 22).

قرارداد (v1, مستند و ثابت):
- tension در [0, 1]:
  tension = 0.2*volume + 0.3*surprise + 0.3*conflict + 0.2*sanctions
  که volume = min(1, n/10)، surprise = میانگین غافلگیری [0,1]،
  conflict = سهم رویدادهای مناقشه، sanctions = min(1, links/3).
- ورودی ناموجود → جزء صفر (نه حدس)؛ n=0 اصلاً assessment نمی‌سازد.
- confidence از تعداد رویداد: ۱→0.3، ۲–۴→0.5، ≥۵→0.7.
- بدون AI؛ فقط ریاضیات قطعی.
"""
from __future__ import annotations

from dataclasses import dataclass


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass(frozen=True)
class TensionStats:
    tension: float
    conflict_share: float
    event_count: int
    sanction_links: int
    confidence: float
    method: str = "tension_v1"


def confidence_for(n: int) -> float:
    if n >= 5:
        return 0.7
    if n >= 2:
        return 0.5
    return 0.3


def tension(
    *,
    n_events: int,
    avg_surprise: float | None,
    conflict_share: float | None,
    sanction_links: int,
) -> TensionStats | None:
    """امتیاز تنش یک بازیگر؛ n=0 → None (بدون assessment)."""
    if n_events <= 0:
        return None
    volume = min(1.0, n_events / 10.0)
    surprise = _clamp01(avg_surprise) if avg_surprise is not None else 0.0
    conflict = _clamp01(conflict_share) if conflict_share is not None else 0.0
    sanctions = min(1.0, sanction_links / 3.0)
    value = round(
        0.2 * volume + 0.3 * surprise + 0.3 * conflict + 0.2 * sanctions, 4
    )
    return TensionStats(
        tension=value,
        conflict_share=round(conflict, 4),
        event_count=n_events,
        sanction_links=sanction_links,
        confidence=confidence_for(n_events),
    )


__all__ = ["TensionStats", "confidence_for", "tension"]
