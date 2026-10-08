"""قواعد Task-specific routing (بند 15 و 62).

نگاشت نقش منطقی → زنجیره‌ی Provider (به‌ترتیب اولویت، برای fallback).
این قواعد فقط داده هستند و از کد جدا نگه داشته می‌شوند.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Route:
    """زنجیره‌ی Provider برای یک نقش/وظیفه."""

    role: str
    providers: list[str] = field(default_factory=list)  # به ترتیب fallback
    model: str | None = None  # مدل مشخص (اختیاری) برای این نقش


# نقش‌ها به‌صورت پیش‌فرض خالی‌اند تا زنجیره از تنظیمات ساخته شود.
# اگر نقش تعریف‌نشده باشد، AI_DEFAULT_PROVIDER استفاده می‌شود.
DEFAULT_ROUTES: dict[str, Route] = {
    "fast_extraction": Route("fast_extraction", []),
    "deep_analysis": Route("deep_analysis", []),
    "critic": Route("critic", []),
    "report": Route("report", []),
    "default": Route("default", []),
}


def resolve_route(role: str | None, task: str | None) -> Route:
    """نقش/وظیفه را به یک زنجیره‌ی Provider نگاشت می‌کند."""
    if role and role in DEFAULT_ROUTES:
        return DEFAULT_ROUTES[role]
    if task and task in DEFAULT_ROUTES:
        return DEFAULT_ROUTES[task]
    return DEFAULT_ROUTES["default"]
