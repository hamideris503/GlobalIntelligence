"""Priority engine — قواعد قطعی P0..P4 با نرمال‌سازی فارسی.

متن خام تغییر نمی‌کند؛ فقط نسخه نرمال برای تطبیق ساخته می‌شود.
score بالا به‌تنهایی به معنی confidence بالا نیست؛ هر دو جدا ذخیره می‌شوند.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from source_bot.config import BotSettings

LEVELS = ("P0", "P1", "P2", "P3", "P4")


def is_valid_level(value: object) -> bool:
    """آیا مقدار دقیقاً یکی از سطوح مجاز P0..P4 است؟ (بدون نرمال‌سازی یا حدس)"""
    return isinstance(value, str) and value in LEVELS

# گروه‌های واژگانی موتور قواعد — تنها منبع: config/priority_keywords.toml.
# نگاشت گروه→وزن و مرزِ کد در score_item است (الگوریتم امتیازدهی تغییر نمی‌کند).
KEYWORD_GROUPS = ("urgent_fa", "urgent_en", "high_fa", "high_en", "conflict")


class PriorityKeywordsError(RuntimeError):
    """config/priority_keywords.toml ناقص یا خراب است — هیچ fallback بی‌صدایی نیست."""


def _keywords_path() -> str:
    """مسیر مطلق config/، مستقل از working directory جاری."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(repo_root, "config", "priority_keywords.toml")


def load_priority_keywords(path: str | None = None) -> dict[str, list[str]]:
    """خواندن گروه‌های واژگانی از TOML؛ خطای صریح در نبود/خرابی هر گروه."""
    import tomllib

    target = path or _keywords_path()
    try:
        with open(target, "rb") as fh:
            data = tomllib.load(fh)
    except FileNotFoundError as exc:
        raise PriorityKeywordsError(f"priority keywords file not found: {target}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise PriorityKeywordsError(f"invalid TOML in {target}: {exc}") from exc
    groups: dict[str, list[str]] = {}
    for name in KEYWORD_GROUPS:
        value = data.get(name)
        if not isinstance(value, list) or not all(
            isinstance(word, str) and word.strip() for word in value
        ):
            raise PriorityKeywordsError(f"group '{name}' missing or invalid in {target}")
        groups[name] = list(value)
    return groups


_KEYWORDS_CACHE: dict[str, list[str]] | None = None


def get_priority_keywords() -> dict[str, list[str]]:
    """کش فرایندی کلیدواژه‌ها — فایل یک بار در عمر پروسه خوانده می‌شود."""
    global _KEYWORDS_CACHE
    if _KEYWORDS_CACHE is None:
        _KEYWORDS_CACHE = load_priority_keywords()
    return _KEYWORDS_CACHE


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


# آستانهٔ تک‌منبعی اطمینان قواعد: پایین‌تر از این مقدار تصمیم قواعد قطعی نیست.
# مسیر عادی ingestion و Source Bot هر دو از همین یک مقدار استفاده می‌کنند.
UNRELIABLE_CONFIDENCE = 0.3


# قرارداد یکسان provenance اولویت، مشترک مسیر عادی ingestion و Source Bot.
def priority_provenance(
    *,
    rules_confidence: float | None = None,
    ai: dict | None = None,
) -> dict:
    """کلیدهای provenance در doc_metadata — فقط از نتیجهٔ واقعی، بدون مقدار جعلی.

    منشأ تصمیم نهایی فقط از خودِ تصمیم مشتق می‌شود (نه از نام وضعیت عملیاتی):
    - پاسخ معتبر و پذیرفته‌شدهٔ AI → `ai`؛
    - وگرنه confidence قواعد ≥ `UNRELIABLE_CONFIDENCE` → `rules`؛
    - وگرنه → `pending`: هیچ تصمیم قطعی‌ای وجود ندارد، پس `priority_confidence`
      null می‌ماند و confidence قواعد در `rules_priority_confidence` جدا ثبت می‌شود.
    - `ai` فقط پاسخ معتبر و پذیرفته‌شده است؛ پاسخ mock/نامعتبر هرگز اینجا نمی‌آید.
    - `priority_score` همیشه امتیاز موتور قواعد است؛ `priority_score_source` آن را
      صریح می‌کند تا با سطح AI‌محور اشتباه گرفته نشود.
    """
    accepted = ai if isinstance(ai, dict) else None
    if accepted is not None:
        decision = "ai"
    elif rules_confidence is not None and rules_confidence >= UNRELIABLE_CONFIDENCE:
        decision = "rules"
    else:
        decision = "pending"
    ai_conf = accepted.get("confidence") if accepted else None
    return {
        "priority_decision_source": decision,
        "priority_score_source": "rules",
        "priority_confidence": (None if decision == "pending"
                                else (ai_conf if accepted else rules_confidence)),
        "rules_priority_confidence": rules_confidence,
        "ai_priority_confidence": ai_conf,
        "ai_priority_reason": accepted.get("reason") if accepted else None,
        "ai_priority_reason_codes": (
            [str(c) for c in accepted.get("reason_codes") or []] if accepted else None
        ),
    }


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
    keywords: dict[str, list[str]] | None = None,
) -> PriorityResult:
    s = settings or BotSettings()
    kw = keywords if keywords is not None else get_priority_keywords()
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
    if _any_kw(words, norm, kw["urgent_fa"]) or _any_kw(words, text.lower(), kw["urgent_en"]):
        score += 45.0
        codes.append("URGENT_KEYWORD")
    elif _any_kw(words, norm, kw["high_fa"]) or _any_kw(words, text.lower(), kw["high_en"]):
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
    if _any_kw(words, norm, kw["conflict"]) or _any_kw(words, text.lower(), kw["conflict"]):
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
