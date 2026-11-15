"""نگهبان ادعاهای مستندشده ─ هر «FIXED» در بک‌لاگ باید یک واقعیت کد پشتش باشد.

علت وجود این فایل: در بازبینی ۱۴ نوامبر ۲۰۲۶ معلوم شد چند قلم بک‌لاگ کهنه
بودند (F-11 در واقع با `FOR UPDATE SKIP LOCKED` حل شده بود) و دو ادعای امنیتی
(`GI-SEC-001`, `GI-SEC-002`) از grep ناقص آمده بودند. این تست‌ها همان
واقعیت‌هایی را قفل می‌کنند که مستندات به آن‌ها استناد می‌کند.

Offline only: in-memory SQLite، بدون شبکه، بدون تراکنش باز.
"""
from __future__ import annotations

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session as SASession

from backend.ai.dispatch.service import DispatchService
from backend.auth.deps import required_role
from tests.conftest import TestingSession


def test_claimable_statement_uses_skip_locked(monkeypatch) -> None:
    """F-11: ردیف‌های قابل‌claim با `FOR UPDATE SKIP LOCKED` انتخاب می‌شوند.

    این تست SQL کامپایل‌شده برای دیالکت PostgreSQL را می‌سنجد؛ روی SQLite همین
    عبارت no-op است، پس سنجش رفتاری صرفاً در لاین PG معنا داشت.
    """
    captured: list[object] = []
    original = SASession.execute

    def spy(self, statement, *args, **kwargs):  # noqa: ANN001 - امضای SQLAlchemy
        captured.append(statement)
        return original(self, statement, *args, **kwargs)

    monkeypatch.setattr(SASession, "execute", spy)
    db = TestingSession()
    try:
        DispatchService(db).claimable("event_extraction")
    finally:
        db.close()

    selects = [s for s in captured if getattr(s, "is_select", False)]
    assert selects, "claimable باید حداقل یک SELECT اجرا کند"
    sql = str(selects[-1].compile(dialect=postgresql.dialect())).upper()
    assert "FOR UPDATE" in sql, sql
    assert "SKIP LOCKED" in sql, sql


def test_test_deliver_requires_admin() -> None:
    """GI-SEC-002: `POST /api/alerts/test-deliver/{channel}` گیت admin دارد.

    گیت از طریق `access_guard` و `required_role` اعمال می‌شود، نه یک decorator
    اختصاصی روی همان تابع؛ همین موضوع باعث ادعای غلط «بدون گیت Admin» شده بود.
    """
    assert required_role("POST", "/api/alerts/test-deliver/email") == "admin"
    assert required_role("POST", "/api/alerts/test-deliver/slack") == "admin"
    # کنترل مثبت: مسیر نوشتن تحلیل‌گر نباید در این تغییر به admin ارتقا یافته باشد.
    assert required_role("POST", "/api/alerts/evaluate") == "analyst"
    assert required_role("GET", "/api/alerts") == "viewer"


def test_documented_test_hygiene_fixes_still_hold() -> None:
    """F-05/F-10: دو اصلاح مستندشدهٔ هارنس نباید بی‌صدا حذف شوند."""
    import os
    from pathlib import Path

    conftest_source = Path(__file__).with_name("conftest.py").read_text(encoding="utf-8")
    assert '.set(host="127.0.0.1")' in conftest_source, "F-05: DSN لاین PG باید IP literal شود"
    assert "PYTEST_DEBUG_TEMPROOT" in conftest_source, "F-10: ریشهٔ temp اختصاصی هر اجرا"
    assert os.environ.get("PYTEST_DEBUG_TEMPROOT", "").find("gi-pytest-") >= 0, (
        "F-10: ریشهٔ temp اختصاصی همین اجرا باید فعال باشد"
    )


def test_no_sqlite_only_assertions_remain() -> None:
    """F-07: تست‌ها نباید صراحتاً SQLite را assert کنند (روی لاین PG می‌شکنند)."""
    from pathlib import Path

    tests_dir = Path(__file__).parent
    # الگو تکه‌تکه ساخته می‌شود تا خود همین فایل به‌عنوان متخلف شناسایی نشود.
    needle_single = "assert " + "'sqlite' in"
    needle_double = "assert " + '"sqlite" in'
    offenders: list[str] = []
    for path in tests_dir.glob("test_*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if needle_single in text or needle_double in text:
            offenders.append(path.name)
    assert offenders == [], f"assert وابسته به SQLite: {offenders}"
