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
        # آستانه‌های اولویت (قابل تنظیم)
        self.th_p0 = _float("SOURCE_BOT_TH_P0", 90.0)
        self.th_p1 = _float("SOURCE_BOT_TH_P1", 75.0)
        self.th_p2 = _float("SOURCE_BOT_TH_P2", 50.0)
        self.th_p3 = _float("SOURCE_BOT_TH_P3", 25.0)
        # AI fallback فقط در عدم قطعیت
        self.ai_min_confidence = _float("SOURCE_BOT_AI_MIN_CONF", 0.55)
        self.ai_border_margin = _float("SOURCE_BOT_AI_MARGIN", 7.0)
        self.ai_enabled = os.getenv("SOURCE_BOT_AI_ENABLED", "true").lower() != "false"


def get_bot_settings() -> BotSettings:
    return BotSettings()
