"""وابستگی‌های احراز هویت (حداقلی — بند 69).

روش: هدر `X-API-Key`. در production باید مقدار قوی تنظیم شود.
"""
from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from backend.core.config import get_settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """بررسی کلید API. اگر API_KEY تنظیم نشده باشد، در development رد می‌شود."""
    settings = get_settings()
    expected = settings.api_key

    # اگر کلیدی تنظیم نشده باشد:
    if not expected:
        if settings.app_env == "production":
            raise HTTPException(status_code=500, detail="API_KEY not configured")
        return  # در development آزاد

    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="invalid or missing API key")
