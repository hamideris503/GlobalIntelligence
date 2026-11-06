"""Logging setup.

لاگ ساختاریافته و ساده. سطح لاگ از تنظیمات خوانده می‌شود. هر خط لاگ شناسه‌ی
درخواست فعلی (`request_id`) را هم دارد تا خطا و لاگ سرور با یک شناسه به هم
وصل شوند (میان‌افزار در `backend/api/errors.py` آن را ست می‌کند).
"""
from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

from backend.core.config import get_settings

# پیش‌فرض "-" یعنی خارج از چرخه‌ی درخواست (startup، jobها)
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIDFilter(logging.Filter):
    """`request_id` را به هر رکورد لاگ اضافه می‌کند."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging() -> None:
    """پیکربندی ریشه‌ی لاگ‌ها (idempotent)."""
    settings = get_settings()
    root = logging.getLogger()
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIDFilter())
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | rid=%(request_id)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
