"""قرارداد UI ↔ API برای جریان‌های Auth (WP-04.4).

این تست به‌جای کلیک کردن در مرورگر، قرارداد ایستا را قفل می‌کند: هر فرم Auth
باید به endpoint واقعی و با همان کلیدهای payload وصل باشد، و UI باید حالت
«ایمیل پیکربندی نشده» را صریح نمایش دهد — نه تأیید ساختگی.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

UI = Path(__file__).resolve().parents[1] / "backend" / "static" / "index.html"

# (endpoint, payload keys لازم در همان فراخوانی)
AUTH_CALLS: list[tuple[str, tuple[str, ...]]] = [
    ("/api/auth/session", ("username", "password")),
    ("/api/auth/register", ("email", "username", "password", "confirm_password")),
    ("/api/auth/forgot-username", ("email",)),
    ("/api/auth/forgot-password", ("email",)),
    ("/api/auth/reset-password", ("token", "password", "confirm_password")),
    ("/api/auth/verify-email", ("token",)),
    ("/api/auth/me", ()),
]


@pytest.fixture(scope="module")
def html() -> str:
    return UI.read_text(encoding="utf-8", errors="ignore")


@pytest.mark.parametrize(("endpoint", "keys"), AUTH_CALLS)
def test_ui_calls_real_auth_endpoint(html: str, endpoint: str, keys: tuple[str, ...]) -> None:
    offsets = [m.start() for m in re.finditer(re.escape(endpoint), html)]
    assert offsets, f"UI هیچ فراخوانی‌ای برای {endpoint} ندارد"
    candidates = [html[max(0, i - 400): i + 700] for i in offsets]
    assert any(all(key in window for key in keys) for window in candidates), (
        f"هیچ فراخوانی {endpoint} کلیدهای payload {keys} را با هم نمی‌فرستد"
    )


def test_ui_renders_not_configured_delivery_state(html: str) -> None:
    assert "EMAIL_DELIVERY_NOT_CONFIGURED" in html, (
        "UI حالت ارسال‌نشدن ایمیل را تشخیص نمی‌دهد؛ خطر نمایش موفقیت ساختگی"
    )


def test_ui_has_no_fake_verification_shortcut(html: str) -> None:
    # تأیید باید از توکن واقعی رد شود، نه از یک مسیر محلی بدون token.
    assert "/api/auth/verify-email" in html
    for shortcut in ("verified=true", "email_verified = true"):
        assert shortcut not in html


def test_ui_deep_links_are_served_by_backend() -> None:
    main = (Path(__file__).resolve().parents[1] / "backend" / "main.py").read_text(
        encoding="utf-8", errors="ignore"
    )
    for route in ("/verify-email", "/reset-password"):
        assert route in main, f"لینک ایمیل {route} نباید 404 بدهد"
