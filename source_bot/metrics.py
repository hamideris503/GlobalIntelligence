"""Metrics — آمار دریافت، خطا، تکراری، اولویت، AI fallback."""
from __future__ import annotations

from dataclasses import dataclass, field


def _token(value: object) -> int | None:
    """توکن گزارش‌شده: فقط int نامنفی واقعی؛ هر چیز دیگر = ناموجود."""
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


@dataclass
class SourceMetrics:
    """شمارندهٔ یک منبع در یک اجرا — تنها منبع گزارش روزانهٔ هر منبع.

    هر فیلد فقط از رویداد واقعی همان منبع پر می‌شود؛ `duration_ms=None` یعنی
    «اندازه‌گیری‌نشده» (مثلاً فراخوانی مستقیم `run_source` در تست)، نه صفر.
    """
    ok: bool = False              # منبع تا انتهای چرخه بدون خطا رفت
    fetch_ok: bool = False        # آخرین تلاش fetch موفق بود
    fetch_attempts: int = 0       # تلاش‌های fetch؛ retry = attempts-1
    fetched: int = 0              # آیتم‌های برگشتی از fetch
    items_skipped_limit: int = 0  # آیتم‌های fetch‌شده که به سقف --items نرسیدند
    stored: int = 0               # اسناد تازه‌ذخیره‌شده
    duplicates: int = 0           # تکراری واقعی (درون batch یا همان منبع در DB)
    rejected_keyless: int = 0     # بی‌هویت (نه تکراری) — جدا شمرده می‌شود
    by_priority: dict[str, int] = field(default_factory=dict)
    ai_used: int = 0              # سطح از AI پذیرفته شد
    ai_fallback: int = 0          # AI در دسترس/mock نبود → قواعد ماند
    # --- مصرف واقعی AI (فقط مقادیر گزارش‌شدهٔ provider؛ None/غایب = ناموجود) ---
    ai_calls: int = 0             # فراخوانی‌های سطح Source Bot (هر آیتم یک‌بار)
    ai_ok: int = 0                # پاسخ واقعی و قابل‌استفاده
    ai_failed: int = 0            # خطا/timeout/خروجی نامعتبر → قواعد ماند
    ai_mock: int = 0              # پاسخ mock (مصرف واقعی نیست)
    ai_providers: dict[str, int] = field(default_factory=dict)
    ai_usage_events: int = 0      # پاسخ‌های با usage کامل (ورودی+خروجی)
    ai_usage_missing: int = 0     # پاسخ‌های بدون usage کامل
    ai_tokens_in: int = 0
    ai_tokens_out: int = 0
    ai_tokens_total: int = 0
    ai_cost_usd: float | None = None   # فقط اگر پاسخ هزینهٔ معتبر گزارش کند
    ai_cost_events: int = 0
    pending: int = 0              # ذخیره‌شده‌های با priority_decision_source=pending
    duration_ms: int | None = None

    def record_ai(self, result: dict | None) -> None:
        """ثبت یک فراخوانی AI: شمارش رویداد + مصرف واقعی همان پاسخ.

        یک فراخوانی=یک ثبت (بدون توجه به retry داخلی Gateway که پاسخ نهایی
        را برمی‌گرداند)؛ مصرف mock هرگز با مصرف واقعی جمع نمی‌شود.
        """
        self.ai_calls += 1
        if result is None:
            self.ai_failed += 1
            return
        if result.get("is_mock"):
            self.ai_mock += 1
            return
        self.ai_ok += 1
        usage = result.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        provider = str(usage.get("provider") or "unknown")
        self.ai_providers[provider] = self.ai_providers.get(provider, 0) + 1
        tokens_in = _token(usage.get("prompt_tokens"))
        tokens_out = _token(usage.get("completion_tokens"))
        total = _token(usage.get("total_tokens"))
        if tokens_in is None or tokens_out is None:
            self.ai_usage_missing += 1
        else:
            self.ai_usage_events += 1
            self.ai_tokens_in += tokens_in
            self.ai_tokens_out += tokens_out
            self.ai_tokens_total += total if total is not None else tokens_in + tokens_out
        cost = usage.get("cost_estimate")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            self.ai_cost_events += 1
            self.ai_cost_usd = round((self.ai_cost_usd or 0.0) + float(cost), 6)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "fetch_ok": self.fetch_ok,
            "fetch_attempts": self.fetch_attempts,
            "fetched": self.fetched,
            "items_skipped_limit": self.items_skipped_limit,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "rejected_keyless": self.rejected_keyless,
            "by_priority": self.by_priority,
            "ai_used": self.ai_used,
            "ai_fallback": self.ai_fallback,
            "ai_calls": self.ai_calls,
            "ai_ok": self.ai_ok,
            "ai_failed": self.ai_failed,
            "ai_mock": self.ai_mock,
            "ai_providers": self.ai_providers,
            "ai_usage_events": self.ai_usage_events,
            "ai_usage_missing": self.ai_usage_missing,
            "ai_tokens_in": self.ai_tokens_in,
            "ai_tokens_out": self.ai_tokens_out,
            "ai_tokens_total": self.ai_tokens_total,
            "ai_cost_usd": self.ai_cost_usd,
            "ai_cost_events": self.ai_cost_events,
            "pending": self.pending,
            "duration_ms": self.duration_ms,
        }


@dataclass
class BotMetrics:
    sources_checked: int = 0
    sources_ok: int = 0
    sources_failed: dict[str, str] = field(default_factory=dict)
    fetched: int = 0
    stored: int = 0
    duplicates: int = 0
    items_skipped_limit: int = 0  # جمع skipped هر منبع (شفاف‌سازی fetched − پردازش‌شده)
    stopped: bool = False         # اجرا با درخواست توقف قطع شد → نتیجهٔ ناقص است
    by_priority: dict[str, int] = field(default_factory=dict)
    ai_used: int = 0
    ai_fallback: int = 0
    # تفکیک هر منبع در همین اجرا؛ پیش‌نیاز گزارش روزانه (بدون جدول جدید).
    by_source: dict[str, SourceMetrics] = field(default_factory=dict)

    def source(self, name: str) -> SourceMetrics:
        """شمارندهٔ همان منبع در همین اجرا (یک نمونه؛ بدون دوباره‌شماری)."""
        return self.by_source.setdefault(str(name), SourceMetrics())

    def as_dict(self) -> dict:
        return {
            "sources_checked": self.sources_checked,
            "sources_ok": self.sources_ok,
            "sources_failed": self.sources_failed,
            "fetched": self.fetched,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "items_skipped_limit": self.items_skipped_limit,
            "stopped": self.stopped,
            "by_priority": self.by_priority,
            "ai_used": self.ai_used,
            "ai_fallback": self.ai_fallback,
            "by_source": {name: m.as_dict() for name, m in self.by_source.items()},
        }
