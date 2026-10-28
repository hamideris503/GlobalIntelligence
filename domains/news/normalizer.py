"""Normalization — یکسان‌سازی آیتم خام به شکل استاندارد (Phase 8).

مسئول:
- پاک‌سازی متن و title
- محاسبه‌ی hash و content_hash (برای dedup در Phase 9)
- تشخیص زبان (ساده و heuristic — در فاز بعدی می‌تواند دقیق‌تر شود)
- ثبت زمان‌های Point-in-Time: published_at / retrieved_at / available_at / observed_at
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import unescape
from urllib.parse import urlparse

from domains.news.fetchers import RawItem

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_PERSIAN_RE = re.compile(r"[\u0600-\u06FF]")
# مرز جمله: فقط وقتی نشانه با فاصله دنبال شود؛ «3.14» و URL/دامنه (بدون فاصله پس از نقطه) نمی‌شکنند.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?؟؛۔])\s+")
# دست‌کم یک نویسهٔ محتوایی (لاتین/رقم/عربی-فارسی) لازم است تا خلاصهٔ ساختگی ساخته نشود.
_CONTENT_RE = re.compile(r"[0-9A-Za-z\u0600-\u06FF]")
# سقف موجود `Article.summary` در classifier._apply — مرجع مشترک برای UI/API.
SUMMARY_MAX_CHARS = 2000


def clean_text(text: str | None) -> str | None:
    """حذف تگ‌های HTML و فشرده‌سازی فاصله‌ها."""
    if not text:
        return None
    plain = unescape(_TAG_RE.sub(" ", text))
    plain = _WS_RE.sub(" ", plain).strip()
    return plain or None


def deterministic_summary(text: str | None, *, limit: int = SUMMARY_MAX_CHARS) -> str | None:
    """خلاصهٔ قطعی از جمله‌های ابتدایی متن پاک‌شده — بدون AI/شبکه/مدل.

    - ورودی باید متن پاک‌شده باشد (خروجی `clean_text`)، نه HTML/`raw_payload`.
    - مرز جمله: `.` `!` `?` `؟` `؛` `۔` فقط وقتی با فاصله دنبال شوند؛ پس اعداد
      اعشاری/تاریخ/URL بی‌دلیل نمی‌شکنند.
    - متن کوتاه‌تر از `limit` دست‌نخورده برمی‌گردد؛ در غیر این صورت فقط تا مرز
      جمله و حداکثر `limit` کاراکتر (پیش‌فرض = سقف موجود Article.summary) کوتاه می‌شود.
    - متن خالی/بی‌محتوا → None؛ هرگز خلاصهٔ ساختگی نمی‌سازد.
    """
    if not text:
        return None
    cleaned = _WS_RE.sub(" ", text).strip()
    if not cleaned or not _CONTENT_RE.search(cleaned):
        return None
    if len(cleaned) <= limit:
        return cleaned

    out: list[str] = []
    total = 0
    for sentence in (part.strip() for part in _SENTENCE_SPLIT_RE.split(cleaned)):
        if not sentence:
            continue
        extra = len(sentence) + (1 if out else 0)
        if out and total + extra > limit:
            break
        out.append(sentence)
        total += extra
        if total >= limit:
            break
    result = " ".join(out).strip()
    if not result:
        return None
    if len(result) > limit:  # تنها یک جملهٔ بلندتر از سقف: برش در مرز واژه
        head = result[:limit]
        cut = head.rfind(" ")
        result = (head[:cut] if cut > 0 else head).rstrip()
    return result or None


def detect_language(text: str | None) -> str | None:
    """تشخیص ساده‌ی زبان بر اساس دامنه‌ی یونیکد."""
    if not text:
        return None
    if _PERSIAN_RE.search(text):
        return "fa"
    return "en"


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def url_hash(url: str | None) -> str | None:
    return sha256(url) if url else None


def content_hash(title: str | None, body: str | None) -> str | None:
    payload = f"{(title or '').strip()}|{(body or '').strip()}"
    return sha256(payload) if payload.strip("|") else None


def payload_hash(raw_payload: str | None) -> str | None:
    """هویت پایدار ردیف‌هایی که URL/عنوان/متن ندارند ولی payload دارند.

    JSON با ترتیب کلید ثابت و بدون فاصله‌ی اضافه سریال می‌شود تا دو نمایش
    هم‌ارز (ترتیب کلید متفاوت، از جمله در دیکشنری‌های تودرتو) یک هش بدهند.
    payload بدون اطلاعات (`""`، `null`، `{}`، `[]`) هویتی نمی‌سازد.
    """
    if not raw_payload:
        return None
    text = raw_payload.strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
    except ValueError:
        return sha256(text)
    canonical = json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return None if canonical in ("null", "{}", "[]") else sha256(canonical)


# آداپتوری که متن سند را با کیفیت بهتری جایگزین می‌کند (مثلاً Source Bot: خلاصهٔ RSS
# → متن کامل مقاله) متنِ هویت‌بخشِ اولیه را زیر این کلید اعلام می‌کند.
IDENTITY_TEXT_KEY = "identity_text"


def identity_url_anchor(url: str | None) -> str | None:
    """لنگر هویت از URL، تنها وقتی متنِ هویت‌بخش در دسترس نیست (فید بدون خلاصه).

    همان قاعدهٔ نرمال‌سازی `source_bot.deduplicator.canonical_url` است (اسکیم
    http/https، هاست کوچک‌شده، حذف fragment و اسلش انتهایی) و **مسیر و query
    دست‌نخورده** می‌مانند: پارامتر رهگیری کورکورانه حذف نمی‌شود چون می‌تواند معنای
    محتوا را عوض کند. محلی نگه داشته شده تا لایهٔ domain به لایهٔ source_bot وابسته
    نشود (import چرخه‌ای). None = بدون لنگر (رفتار قبلی حفظ می‌شود).
    """
    if not url:
        return None
    try:
        p = urlparse(url.strip())
        if p.scheme not in ("http", "https"):
            return None
        path = p.path.rstrip("/") or "/"
        query = f"?{p.query}" if p.query else ""
        return f"{p.scheme}://{(p.hostname or '').lower()}{path}{query}"
    except Exception:  # noqa: BLE001
        return None


def identity_body(raw_text: str | None, metadata: dict | None = None) -> str | None:
    """متنِ لنگرِ هویت: متن اعلام‌شدهٔ آداپتور اگر کلید حاضر باشد، وگرنه متن فعلی.

    «حضور کلید» ملاک است (مقدار می‌تواند تهی باشد)، وگرنه سندِ خلاصه‌محور و
    سندِ متن‌کامل برای یک خبر دو هش متفاوت می‌گرفتند و یک خبر به دو ردیف تبدیل می‌شد.
    """
    meta = metadata if isinstance(metadata, dict) else {}
    if IDENTITY_TEXT_KEY in meta:
        value = meta.get(IDENTITY_TEXT_KEY)
        return value if isinstance(value, str) else None
    return raw_text


def identity_hash(
    title: str | None, body: str | None, raw_payload: str | None = None,
    url: str | None = None,
) -> str | None:
    """هش هویت: الگوی `title|body`؛ فقط اگر هویتی نسازد، از payload پایدار.

    اگر بدنهٔ هویت‌بخش تهی/غایب باشد ولی عنوان موجود باشد (فید بدون `description`،
    مثل ECB)، هش به «عنوان تنها» فرو می‌کاهد و دو خبر هم‌عنوان در یک منبع یک هویت
    می‌گیرند. در این حالت لنگر جانشین از URL canonical ساخته می‌شود. ردیفِ **بی‌عنوان**
    دست‌نخورده می‌ماند: بدون عنوان و بدنه هویتی ساخته نمی‌شود (قرارداد NULL قبلی و
    نگهبان ابهام `_find_created_row` حفظ می‌شود).
    """
    if not (isinstance(body, str) and body.strip()) and isinstance(title, str) and title.strip():
        body = identity_url_anchor(url) or body
    return content_hash(title, body) or payload_hash(raw_payload)


@dataclass
class NormalizedItem:
    title: str | None
    url: str | None
    raw_text: str | None
    language: str | None
    author: str | None
    published_at: datetime | None
    retrieved_at: datetime
    available_at: datetime
    observed_at: datetime
    hash: str | None
    content_hash: str | None
    metadata: dict
    raw_payload: str | None = None


def normalize(item: RawItem, *, retrieved_at: datetime | None = None) -> NormalizedItem:
    """یک RawItem را به شکل استاندارد تبدیل می‌کند.

    Point-in-Time:
    - `retrieved_at` = زمان واقعی دریافت (اکنون).
    - `available_at` = همان retrieved_at؛ چون «چه زمانی ما می‌توانستیم بدانیم»
      لزوماً زمان انتشار نیست و برای محتوای backfill/آینده نباید ادعای دانستن
      در گذشته کنیم (جلوگیری از look-ahead).
    - اگر published_at در آینده باشد (بیش از ۵ دقیقه)، آیتم مشکوک علامت‌گذاری
      و available_at روی retrieved_at می‌ماند.
    """
    now = retrieved_at or datetime.now(UTC)
    title = clean_text(item.title)
    body = clean_text(item.raw_text)

    published_at = item.published_at
    metadata = dict(item.metadata)
    # هویت محتوایی روی متنِ لنگر بسته می‌شود (اگر آداپتور اعلام کرده باشد)، نه روی
    # متن استخراج‌شده؛ `raw_text` ذخیره‌شده دست‌نخورده می‌ماند.
    identity_text = clean_text(identity_body(item.raw_text, metadata))
    if published_at is not None and published_at > now + timedelta(minutes=5):
        metadata["suspicious_future_published_at"] = published_at.isoformat()

    available_at = now  # اصلاح look-ahead: فقط زمانی که واقعاً دریافت شده
    observed_at = now

    return NormalizedItem(
        title=title,
        url=item.url,
        raw_payload=item.raw_payload,
        raw_text=body,
        language=item.language or detect_language(f"{title or ''} {body or ''}"),
        author=item.author,
        published_at=published_at,
        retrieved_at=now,
        available_at=available_at,
        observed_at=observed_at,
        hash=url_hash(item.url),
        content_hash=identity_hash(title, identity_text, item.raw_payload, item.url),
        metadata=metadata,
    )
