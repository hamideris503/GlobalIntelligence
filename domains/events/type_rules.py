"""قواعد قطعی (بدون AI و بدون شبکه) برای تعیین نوع رویداد.

هر نوع یک فهرست کلیدواژه/عبارت با وزن دارد. متن نرمال می‌شود و امتیاز هر نوع
جمع می‌شود. اگر امتیاز کافی نبود یا دو نوع با هم تعارض داشتند (اختلاف کم)،
نتیجه ``unknown`` می‌ماند و دلیل آن در ``type_reason`` ذخیره می‌شود.

این قواعد فقط روی متن صریح رویداد/مقاله کار می‌کنند؛ هیچ استنتاج معنایی ندارند.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TypeRule:
    event_type: str
    keywords: tuple[tuple[str, float], ...]
    # حداقل امتیاز برای پذیرش
    threshold: float = 2.0


# کلیدواژه‌ها به صورت عبارت‌های چندکلمه‌ای می‌توانند باشند؛ ترتیب مهم نیست.
RULES: tuple[TypeRule, ...] = (
    TypeRule("conflict", (
        ("war", 2.0), ("conflict", 2.0), ("ceasefire", 2.0), ("airstrike", 3.0),
        ("air strike", 3.0), ("bombing", 3.0), ("missile", 2.0), ("shelling", 3.0),
        ("invasion", 3.0), ("clash", 2.0), ("troops", 1.0), ("militant", 2.0),
        ("hostage", 2.0), ("kidnap", 2.0), ("genocide", 3.0), ("siege", 2.0),
        ("artillery", 2.0), ("rocket attack", 3.0), ("gunfire", 2.0),
        ("جنگ", 2.0), ("درگیری", 2.0), ("حملهٔ موشکی", 3.0), ("گروگان", 2.0),
    )),
    TypeRule("attacks", (
        ("attack", 2.0), ("shooting", 3.0), ("stabbing", 3.0), ("explosion", 3.0),
        ("blast", 2.0), ("terror", 3.0), ("terrorism", 3.0), ("assassination", 3.0),
        ("ambush", 3.0), ("drone strike", 3.0), ("mass shooting", 3.0),
        ("حمله", 2.0), ("انفجار", 3.0), ("ترور", 3.0), ("暗杀", 3.0),
    )),
    TypeRule("military", (
        ("military", 2.0), ("army", 2.0), ("navy", 2.0), ("air force", 2.0),
        ("pentagon", 2.0), ("soldier", 2.0), ("deployment", 2.0), ("defense", 1.0),
        ("weapon", 1.0), ("exercise", 1.0), ("troop movement", 2.0), ("base", 1.0),
        ("نظامی", 2.0), ("پنتاگون", 2.0), ("ارتش", 2.0),
    )),
    TypeRule("protests", (
        ("protest", 3.0), ("demonstration", 3.0), ("rally", 2.0), ("riot", 3.0),
        ("unrest", 3.0), ("march", 1.0), ("boycott", 2.0), ("sit-in", 2.0),
        ("strike action", 2.0), ("civil unrest", 3.0),
        ("اعتراض", 3.0), ("تجمع", 2.0), ("ناآرامی", 3.0), ("اعتصاب", 2.0),
    )),
    TypeRule("sanctions", (
        ("sanction", 3.0), ("embargo", 3.0), ("export control", 3.0),
        ("asset freeze", 3.0), ("blacklist", 2.0), ("trade restriction", 2.0),
        ("تحریم", 3.0), ("محدودیت تجاری", 2.0),
    )),
    TypeRule("economic", (
        ("economy", 2.0), ("inflation", 3.0), ("gdp", 2.0), ("tariff", 2.0),
        ("recession", 3.0), ("interest rate", 2.0), ("layoff", 2.0), ("layoffs", 2.0),
        ("profit", 1.0), ("market", 1.0), ("stock", 1.0), ("bank", 1.0),
        ("oil price", 2.0), ("trade", 1.0), ("business", 1.0), ("employment", 1.0),
        ("federal reserve", 3.0), ("fed", 2.0), ("earnings", 2.0), ("revenue", 2.0),
        ("merger", 2.0), ("acquisition", 2.0), ("shares", 2.0), ("stocks", 2.0),
        ("اقتصاد", 2.0), ("تورم", 3.0), ("اشتغال", 1.0), ("بازار", 1.0),
    )),
    TypeRule("aviation", (
        ("flight", 2.0), ("airline", 2.0), ("airport", 2.0), ("airspace", 3.0),
        ("aircraft", 2.0), ("plane", 2.0), ("aviation", 3.0), ("air travel", 2.0),
        ("پرواز", 2.0), ("فرودگاه", 2.0), ("هوانوردی", 3.0),
    )),
    TypeRule("maritime", (
        ("ship", 2.0), ("shipping", 3.0), ("naval", 2.0), ("port", 1.0),
        ("strait", 3.0), ("vessel", 2.0), ("maritime", 3.0), ("sea lane", 2.0),
        ("کشتیرانی", 3.0), ("بندر", 1.0), ("دریایی", 2.0),
    )),
    TypeRule("infrastructure", (
        ("infrastructure", 3.0), ("power outage", 3.0), ("blackout", 3.0),
        ("pipeline", 2.0), ("bridge", 1.0), ("grid", 2.0), ("water supply", 2.0),
        ("telecom", 2.0), ("outage", 1.0), ("substation", 2.0),
        ("زیرساخت", 3.0), ("قطعی برق", 3.0), ("پایپلاین", 2.0),
    )),
    TypeRule("natural", (
        ("earthquake", 3.0), ("flood", 3.0), ("wildfire", 3.0), ("storm", 2.0),
        ("hurricane", 3.0), ("tornado", 3.0), ("drought", 3.0), ("volcano", 3.0),
        ("tsunami", 3.0), ("earthquake", 3.0), ("weather", 1.0), ("heatwave", 2.0),
        ("زلزله", 3.0), ("سیل", 3.0), ("آتش‌سوزی", 3.0), ("طوفان", 2.0),
        ("خشکسالی", 3.0), ("آتشفشان", 3.0),
    )),
    TypeRule("cyber", (
        ("cyber", 3.0), ("hack", 3.0), ("ransomware", 3.0), ("data breach", 3.0),
        ("malware", 3.0), ("phishing", 2.0), ("ddos", 3.0), ("cyberattack", 3.0),
        ("سایبری", 3.0), ("هک", 3.0),
    )),
    TypeRule("risk", (
        ("election", 2.0), ("vote", 1.0), ("president", 1.0), ("prime minister", 2.0),
        ("police", 1.0), ("arrest", 2.0), ("lawsuit", 2.0), ("court", 1.0),
        ("judge", 2.0), ("resign", 2.0), ("scandal", 2.0),
        ("parliament", 2.0), ("government", 1.0),
        ("corruption", 2.0), ("prosecutor", 2.0), ("ruling", 1.0),
        ("politics", 1.0), ("policy", 1.0), ("law", 1.0), ("mayor", 2.0),
        ("انتخابات", 2.0), ("رئیس‌جمهور", 1.0), ("دولت", 1.0), ("پارلمان", 2.0),
        ("استعفا", 2.0), ("فساد", 2.0), ("دادگاه", 1.0),
    )),
)

_NORMALIZE_RE = re.compile(r"[\s_\-/.,:;!?\"'()\[\]{}]+")


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    return _NORMALIZE_RE.sub(" ", text.strip().lower()).strip()


def classify_event_type(text: str | None) -> tuple[str, str, float, list[str]]:
    """Return (event_type, reason, score, matched_keywords).

    ``event_type`` is ``"unknown"`` when no rule reaches its threshold or two
    rules are too close.
    """
    norm = _normalize(text)
    if not norm:
        return "unknown", "empty_text", 0.0, []

    scores: dict[str, float] = {}
    matched: dict[str, list[str]] = {}
    for rule in RULES:
        s = 0.0
        ms: list[str] = []
        for kw, w in rule.keywords:
            nkw = _normalize(kw)
            if nkw and nkw in (" " + norm + " "):
                s += w
                ms.append(kw)
        if s > 0:
            scores[rule.event_type] = s
            matched[rule.event_type] = ms

    if not scores:
        return "unknown", "no_keyword_match", 0.0, []

    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    best_type, best_score = ordered[0]
    second_score = ordered[1][1] if len(ordered) > 1 else 0.0
    rule = next(r for r in RULES if r.event_type == best_type)

    if best_score < rule.threshold:
        return "unknown", f"score_below_threshold ({best_score:.1f}<{rule.threshold:.1f})", best_score, matched.get(best_type, [])
    if (best_score - second_score) < 1.0:
        return "unknown", f"ambiguous ({best_type}={best_score:.1f} vs {ordered[1][0]}={second_score:.1f})", best_score, matched.get(best_type, [])
    return best_type, f"matched: {', '.join(matched.get(best_type, []))}", best_score, matched.get(best_type, [])
