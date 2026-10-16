"""Priority engine — قواعد قطعی P0..P4 با نرمال‌سازی فارسی.

متن خام تغییر نمی‌کند؛ فقط نسخه نرمال برای تطبیق ساخته می‌شود.
score بالا به‌تنهایی به معنی confidence بالا نیست؛ هر دو جدا ذخیره می‌شوند.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from source_bot.config import BotSettings

LEVELS = ("P0", "P1", "P2", "P3", "P4")

URGENT_FA = [
    "فوری", "اضطراری", "بحران", "هشدار", "زلزله", "جنگ", "حمله", "تحریم",
    "ورشکستگی", "فروپاشی", "تعطیلی", "انفجار", "کودتا", "آتش",
]
URGENT_EN = [
    "breaking", "urgent", "emergency", "crisis", "alert", "earthquake",
    "war", "attack", "sanction", "bankrupt", "collapse", "explosion", "coup",
]

HIGH_FA = ["بانک مرکزی", "نرخ بهره", "تورم", "انتخابات", "توافق", "مذاکره", "نفت", "ارز"]
HIGH_EN = ["central bank", "interest rate", "inflation", "election", "agreement", "oil price", "exchange rate"]

_CONFLICT = ["contradict", "disputed", "conflict", "متناقض", "اختلاف"]


def normalize_fa(text: str) -> str:
    t = text.replace("ي", "ی").replace("ك", "ک")
    t = re.sub(r"[\u200c\s]+", " ", t)
    return t.strip().lower()


def _any_kw(tokens: set[str], text: str, keywords: list[str]) -> bool:
    """تک‌واژه فقط به‌عنوان واژه‌ی مستقل؛ چندواژه‌ای رفتار قبلی (زیررشته).

    نرمال‌سازی فقط روی نسخه‌ی تطبیق است؛ متن خام دست نمی‌خورد.
    """
    return any((w in tokens) if " " not in w else (w in text)
               for w in keywords)


@dataclass
class PriorityResult:
    level: str
    score: float
    confidence: float
    reason_codes: list[str] = field(default_factory=list)
    needs_ai: bool = False


def _level_for(score: float, s: BotSettings) -> str:
    if score >= s.th_p0:
        return "P0"
    if score >= s.th_p1:
        return "P1"
    if score >= s.th_p2:
        return "P2"
    if score >= s.th_p3:
        return "P3"
    return "P4"


def score_item(
    *,
    title: str | None,
    body: str | None,
    source_priority: int | None = None,
    category: str | None = None,
    published_at: datetime | None = None,
    has_author: bool = False,
    settings: BotSettings | None = None,
) -> PriorityResult:
    s = settings or BotSettings()
    text = f"{title or ''} {body or ''}"
    norm = normalize_fa(text)
    words = set(re.findall(r"\w+", norm)) | set(re.findall(r"\w+", text.lower()))
    score = 20.0
    codes: list[str] = []

    if source_priority is not None:
        # priority کوچک‌تر = مهم‌تر (۱ مهم‌ترین)
        score += max(0.0, (6 - min(max(source_priority, 1), 5)) * 4.0)
        codes.append("SOURCE_WEIGHT")
    if category in ("economy", "markets", "geopolitics", "alert"):
        score += 8.0
        codes.append("HIGH_CATEGORY")
    if _any_kw(words, norm, URGENT_FA) or _any_kw(words, text.lower(), URGENT_EN):
        score += 45.0
        codes.append("URGENT_KEYWORD")
    elif _any_kw(words, norm, HIGH_FA) or _any_kw(words, text.lower(), HIGH_EN):
        score += 22.0
        codes.append("HIGH_IMPACT")
    if published_at is not None:
        try:
            age_h = (datetime.now(UTC) - published_at).total_seconds() / 3600.0
            if age_h < 0:
                codes.append("FUTURE_DATE_SUSPICIOUS")
            elif age_h <= 6:
                score += 10.0
                codes.append("FRESH")
            elif age_h > 72:
                score -= 8.0
                codes.append("STALE")
        except Exception:  # noqa: BLE001
            codes.append("BAD_DATE")
    else:
        codes.append("NO_DATE")
    if title and body and len(body) > 200:
        score += 5.0
        codes.append("COMPLETE")
    elif not body:
        score -= 10.0
        codes.append("INCOMPLETE")
    if has_author:
        score += 2.0
    if _any_kw(words, norm, _CONFLICT) or _any_kw(words, text.lower(), _CONFLICT):
        codes.append("CONFLICT_SIGNAL")

    score = max(0.0, min(100.0, score))
    level = _level_for(score, s)

    # confidence: پایین اگر نزدیک مرز، بدون تاریخ، ناقص، یا سیگنال متعارض
    conf = 0.85
    dist_to_border = min(
        abs(score - s.th_p0), abs(score - s.th_p1),
        abs(score - s.th_p2), abs(score - s.th_p3),
    )
    if dist_to_border <= s.ai_border_margin:
        conf -= 0.3
        codes.append("NEAR_BORDER")
    if "NO_DATE" in codes or "INCOMPLETE" in codes:
        conf -= 0.2
    if "CONFLICT_SIGNAL" in codes:
        conf -= 0.25
    conf = max(0.05, min(0.95, conf))
    needs_ai = conf < s.ai_min_confidence or "NEAR_BORDER" in codes or "CONFLICT_SIGNAL" in codes
    return PriorityResult(level, round(score, 1), round(conf, 2), codes, needs_ai)
