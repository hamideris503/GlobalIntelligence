"""Analytics — توابع خالص انتقال اثر (Phase 34).

قرارداد (v1, مستند و ثابت):
- کانال‌ها و وزن exposure (ثابت کارشناسی v1):
  - energy: 0.9 (وابستگی درآمد نفتی)
  - rates: 0.6 (نقدینگی جهانی و هزینه‌ی تأمین مالی)
  - geopolitical: 0.8 (تحریم و تنش مستقیم)
  - market: 0.5 (سرایت بازارها)
- impact = clamp(input) × exposure؛ input ناموجود → کانال skip (نه صفر).
- confidence: 0.6 با ورودی واقعی.
- بدون AI؛ فقط ریاضیات قطعی.
"""
from __future__ import annotations

from dataclasses import dataclass, field

EXPOSURES = {
    "energy": 0.9,
    "rates": 0.6,
    "geopolitical": 0.8,
    "market": 0.5,
}


@dataclass(frozen=True)
class ChannelImpact:
    channel: str
    input_value: float
    exposure: float
    impact: float
    confidence: float = 0.6
    method: str = "transmission_v1"
    drivers: list[str] = field(default_factory=list)


def transmit(channel: str, input_value: float | None, driver: str) -> ChannelImpact | None:
    """اثر منتقل‌شده‌ی یک کانال؛ ورودی ناموجود → None."""
    if input_value is None or channel not in EXPOSURES:
        return None
    exposure = EXPOSURES[channel]
    clamped = max(0.0, min(1.0, input_value))
    return ChannelImpact(
        channel=channel,
        input_value=round(input_value, 4),
        exposure=exposure,
        impact=round(clamped * exposure, 4),
        drivers=[driver],
    )


__all__ = ["ChannelImpact", "EXPOSURES", "transmit"]
