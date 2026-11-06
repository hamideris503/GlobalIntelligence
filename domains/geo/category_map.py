"""نگاشت قطعی `event_type` به لایه‌های نقشهٔ جهانی (مرحله ۳).

`Event.event_type` یک رشتهٔ آزاد از LLM است؛ هر نگاشت باید صریح و مستند باشد.
دستهٔ ناشناخته حذف می‌شود (به `other` نگاشت نمی‌شود) تا هیچ عارضه‌ای با لایهٔ
حدسی روی نقشه نیاید. هیچ LLM یا قاعدهٔ مبهم در این مسیر نیست.
"""
from __future__ import annotations

import re

# لایه‌های UI (`worldMonitorPage`)؛ `heat`/`routes` خودشان داده تولید نمی‌کنند.
CATEGORIES: frozenset[str] = frozenset({
    "conflict",
    "attacks",
    "military",
    "protests",
    "sanctions",
    "economic",
    "aviation",
    "maritime",
    "infrastructure",
    "natural",
    "cyber",
    "risk",
})

# event_type (نرمال‌شده) -> لایه. مترادف‌ها صریح‌اند؛ اضافه‌کردن مورد تازه
# باید همراه با تست باشد.
CATEGORY_MAP: dict[str, str] = {
    # conflict
    "conflict": "conflict",
    "conflicts": "conflict",
    "armed conflict": "conflict",
    "war": "conflict",
    "civil war": "conflict",
    "ceasefire violation": "conflict",
    "clash": "conflict",
    "clashes": "conflict",
    "border tension": "conflict",
    # attacks
    "attack": "attacks",
    "attacks": "attacks",
    "armed attack": "attacks",
    "bombing": "attacks",
    "explosion": "attacks",
    "terrorism": "attacks",
    "terrorist attack": "attacks",
    "assassination": "attacks",
    "strike": "attacks",
    # military
    "military": "military",
    "military activity": "military",
    "military exercise": "military",
    "troop movement": "military",
    "deployment": "military",
    "drone": "military",
    "air defense": "military",
    # protests
    "protest": "protests",
    "protests": "protests",
    "demonstration": "protests",
    "unrest": "protests",
    "riot": "protests",
    "strike action": "protests",
    "civil unrest": "protests",
    # sanctions
    "sanction": "sanctions",
    "sanctions": "sanctions",
    "embargo": "sanctions",
    "export control": "sanctions",
    "asset freeze": "sanctions",
    # economic
    "economic": "economic",
    "economic activity": "economic",
    "trade": "economic",
    "market": "economic",
    "inflation": "economic",
    "currency": "economic",
    "investment": "economic",
    "supply chain": "economic",
    # aviation
    "aviation": "aviation",
    "flight": "aviation",
    "airspace closure": "aviation",
    "aircraft": "aviation",
    # maritime
    "maritime": "maritime",
    "shipping": "maritime",
    "ship": "maritime",
    "naval": "maritime",
    "port": "maritime",
    "strait": "maritime",
    # infrastructure
    "infrastructure": "infrastructure",
    "power outage": "infrastructure",
    "blackout": "infrastructure",
    "pipeline": "infrastructure",
    "cable": "infrastructure",
    "energy infrastructure": "infrastructure",
    # natural
    "natural": "natural",
    "natural disaster": "natural",
    "earthquake": "natural",
    "flood": "natural",
    "wildfire": "natural",
    "storm": "natural",
    "drought": "natural",
    "volcano": "natural",
    # cyber
    "cyber": "cyber",
    "cyber attack": "cyber",
    "cyber incident": "cyber",
    "data breach": "cyber",
    "outage": "cyber",
    "ransomware": "cyber",
    # risk
    "risk": "risk",
    "instability": "risk",
    "political risk": "risk",
    "sovereign risk": "risk",
    "credit downgrade": "risk",
}

_NORMALIZE_RE = re.compile(r"[\s_\-/]+")


def normalize_event_type(value: str | None) -> str:
    if not value:
        return ""
    return _NORMALIZE_RE.sub(" ", value.strip().lower()).strip()


def category_for(event_type: str | None) -> str | None:
    """لایهٔ متناظر یا `None` برای نوع ناشناخته/خالی."""
    return CATEGORY_MAP.get(normalize_event_type(event_type))
