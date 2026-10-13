"""Metrics — آمار دریافت، خطا، تکراری، اولویت، AI fallback."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BotMetrics:
    sources_checked: int = 0
    sources_ok: int = 0
    sources_failed: dict[str, str] = field(default_factory=dict)
    fetched: int = 0
    stored: int = 0
    duplicates: int = 0
    by_priority: dict[str, int] = field(default_factory=dict)
    ai_used: int = 0
    ai_fallback: int = 0

    def as_dict(self) -> dict:
        return {
            "sources_checked": self.sources_checked,
            "sources_ok": self.sources_ok,
            "sources_failed": self.sources_failed,
            "fetched": self.fetched,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "by_priority": self.by_priority,
            "ai_used": self.ai_used,
            "ai_fallback": self.ai_fallback,
        }
