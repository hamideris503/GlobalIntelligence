"""Tests for smoke-check helpers (Phase 47).

اجرای زنده‌ی staging در تأیید زنده انجام می‌شود، نه pytest.
"""
from __future__ import annotations

from scripts.smoke_check import PROTECTED_CHECKS, PUBLIC_CHECKS, SmokeReport


def test_check_lists_sane() -> None:
    assert len(PUBLIC_CHECKS) >= 2
    assert len(PROTECTED_CHECKS) >= 5
    names = [n for n, _ in PUBLIC_CHECKS + PROTECTED_CHECKS]
    assert len(names) == len(set(names))


def test_report_ok_property() -> None:
    ok = SmokeReport(passed=3, failed=0)
    assert ok.ok is True
    bad = SmokeReport(passed=2, failed=1)
    assert bad.ok is False
    assert bad.as_dict()["failed"] == 1


def test_get_connection_failure() -> None:
    from scripts.smoke_check import _get

    status, detail = _get("http://localhost:9", "/health", None, timeout=2)
    assert status == 0
    assert detail
