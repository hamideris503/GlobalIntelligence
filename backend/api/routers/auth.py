"""Dashboard login — نام کاربری/رمز به‌جای تایپ دستی کلید (Step 8).

طراحی (ADR-STEP8B): پس از تأیید admin، همان API_KEY سرور به حافظه‌ی مرورگر
برگردانده می‌شود (دقیقاً معادل تایپ دستی؛ نه بیشتر). بدون محافظت (خودش ورود است)
ولی با سقف ۱۰ تلاش/دقیقه برای هر IP. در production رمز پیش‌فرض fail-fast می‌شود.
"""
from __future__ import annotations

import secrets
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.core.config import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

_LOGIN_HITS: dict[str, list[float]] = defaultdict(list)
LOGIN_LIMIT_PER_MIN = 10


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


class LoginResponse(BaseModel):
    ok: bool
    api_key: str = ""


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request) -> LoginResponse:
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    hits = [t for t in _LOGIN_HITS[client_ip] if t > now - 60.0]
    if len(hits) >= LOGIN_LIMIT_PER_MIN:
        raise HTTPException(status_code=429, detail="too many login attempts; retry in a minute")
    hits.append(now)
    _LOGIN_HITS[client_ip] = hits

    settings = get_settings()
    user_ok = secrets.compare_digest(payload.username, settings.admin_username or "")
    pass_ok = secrets.compare_digest(payload.password, settings.admin_password or "")
    if not (user_ok and pass_ok):
        raise HTTPException(status_code=401, detail="نام کاربری یا رمز اشتباه است")
    return LoginResponse(ok=True, api_key=settings.api_key or "")
