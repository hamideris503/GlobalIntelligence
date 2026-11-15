"""رگرسیون eligibility آرشیو در برابر ردیف‌های پارک‌شدهٔ dispatch.

باگ واقعی: `DispatchService.mark_blocked` ردیف screening را که پیش‌نیازش در دسترس
نیست (نه LOCAL runtime، نه provider واقعی) عمداً `pending` نگه می‌دارد. آرشیو هر
`pending` را «Job فعال» می‌دید، پس هیچ مقاله‌ای آرشیو نمی‌شد (۱۹ از ۲۰ مقاله در
دیتابیس آزمایشی). این تست‌ها هم استثنا و هم حفظ رفتار قبلی برای Jobهای واقعی را
قفل می‌کنند.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from backend.database.models.article import Article
from backend.database.models.article_dispatch import ArticleDispatch
from domains.archive.service import is_eligible
from tests.conftest import TestingSession
from tests.test_archive_local import _seed_article


def _add_dispatch(article_id: str, *, status: str, last_error: str | None) -> None:
    session = TestingSession()
    try:
        session.add(
            ArticleDispatch(
                article_id=uuid.UUID(article_id),
                task_name="screening@v1",
                status=status,
                attempts=0,
                last_error=last_error,
                next_retry_at=datetime.now(UTC) + timedelta(seconds=30),
            )
        )
        session.commit()
    finally:
        session.close()


def _eligibility(article_id: str):
    session = TestingSession()
    try:
        art = session.get(Article, uuid.UUID(article_id))
        return is_eligible(session, art)
    finally:
        session.close()


def test_blocked_parked_screening_does_not_block_archive():
    aid = _seed_article()
    _add_dispatch(
        aid,
        status="pending",
        last_error="screening_unavailable: LOCAL_DISABLED,AI_ERROR:no_real_provider",
    )
    ok, reasons = _eligibility(aid)
    assert ok is True, reasons


def test_pending_dispatch_without_marker_still_blocks():
    aid = _seed_article()
    _add_dispatch(aid, status="pending", last_error=None)
    ok, reasons = _eligibility(aid)
    assert ok is False
    assert "active_dispatch" in reasons


def test_running_dispatch_still_blocks_even_with_old_error():
    aid = _seed_article()
    _add_dispatch(
        aid,
        status="running",
        last_error="screening_unavailable: LOCAL_DISABLED",
    )
    ok, reasons = _eligibility(aid)
    assert ok is False
    assert "active_dispatch" in reasons


def test_real_screening_failure_blocks_archive():
    aid = _seed_article()
    _add_dispatch(aid, status="retryable", last_error="timeout: upstream 30s")
    ok, reasons = _eligibility(aid)
    assert ok is False
    assert "active_dispatch" in reasons
