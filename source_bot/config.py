"""Bot settings — همه از env با پیش‌فرض امن؛ secret هرگز در کد نیست."""
from __future__ import annotations

import os


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


class BotConfigError(ValueError):
    """پیکربندی ربات نامعتبر است — هیچ fallback بی‌صدایی به پیش‌فرض وجود ندارد."""


def _threshold(name: str, default: float) -> float:
    """آستانهٔ اولویت: عدد در [0, 100]؛ مقدار نامعتبر خطای پیکربندی صریح می‌دهد."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise BotConfigError(f"{name} must be a number within [0, 100], got {raw!r}") from exc
    if not 0.0 <= value <= 100.0:
        raise BotConfigError(f"{name} must be within [0, 100], got {value}")
    return value


def _validate_threshold_order(p0: float, p1: float, p2: float, p3: float) -> None:
    """مرزها باید اکیداً نزولی باشند تا هر سطح مسیر تصمیم واقعی داشته باشد."""
    if not p0 > p1 > p2 > p3:
        raise BotConfigError(
            "priority thresholds must be strictly descending "
            f"(TH_P0 > TH_P1 > TH_P2 > TH_P3), got P0={p0}, P1={p1}, P2={p2}, P3={p3}"
        )


class BotSettings:
    def __init__(self) -> None:
        self.timeout_seconds = _float("SOURCE_BOT_TIMEOUT", 20.0)
        self.max_bytes = _int("SOURCE_BOT_MAX_BYTES", 5_000_000)
        self.max_csv_bytes = _int("SOURCE_BOT_MAX_CSV_BYTES", 10_000_000)
        self.max_pages_per_source = _int("SOURCE_BOT_MAX_PAGES", 20)
        self.max_depth = _int("SOURCE_BOT_MAX_DEPTH", 2)
        self.concurrency = _int("SOURCE_BOT_CONCURRENCY", 4)
        self.request_delay = _float("SOURCE_BOT_DELAY", 1.0)
        self.max_redirects = _int("SOURCE_BOT_MAX_REDIRECTS", 3)
        self.max_retries = _int("SOURCE_BOT_MAX_RETRIES", 2)
        self.per_source_interval = _int("SOURCE_BOT_INTERVAL", 3600)
        # آستانه‌های اولویت (قابل تنظیم؛ نامعتبر/بی‌ترتیب = BotConfigError)
        self.th_p0 = _threshold("SOURCE_BOT_TH_P0", 90.0)
        self.th_p1 = _threshold("SOURCE_BOT_TH_P1", 75.0)
        self.th_p2 = _threshold("SOURCE_BOT_TH_P2", 50.0)
        self.th_p3 = _threshold("SOURCE_BOT_TH_P3", 25.0)
        _validate_threshold_order(self.th_p0, self.th_p1, self.th_p2, self.th_p3)
        # AI fallback فقط در عدم قطعیت
        self.ai_min_confidence = _float("SOURCE_BOT_AI_MIN_CONF", 0.55)
        self.ai_border_margin = _float("SOURCE_BOT_AI_MARGIN", 7.0)
        self.ai_enabled = os.getenv("SOURCE_BOT_AI_ENABLED", "true").lower() != "false"


def get_bot_settings() -> BotSettings:
    return BotSettings()
