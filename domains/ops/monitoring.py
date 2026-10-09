"""Monitoring checks — چک‌های خالص مانیتورینگ production (Phase 50).

قرارداد (v1, آستانه‌های مستند و ثابت):
- pipeline_lag (ساعت از آخرین مقاله): ‎≤24 pass | ‎≤72 warn | وگرنه fail؛ بدون داده → warn.
- classify_backlog (pending): ‎≤50 pass | ‎≤200 warn | وگرنه fail.
- unprocessed (رویداد/ادعای پردازش‌نشده): ‎≤20 pass | ‎≤100 warn | وگرنه fail.
- error_rate (خطا در ۵۰ job اخیر): ‎≤0.2 pass | ‎≤0.5 warn | وگرنه fail؛ بدون job → warn.
- active_alerts: همیشه pass اطلاعاتی (هشدار سیگنال است، نه خرابی).
- db_ok: True → pass، وگرنه fail.
- وضعیت کلی = بدترین چک. بدون AI.
"""
from __future__ import annotations

from dataclasses import dataclass

SEVERITY_RANK = {"pass": 0, "warn": 1, "fail": 2}


@dataclass(frozen=True)
class MonitorCheck:
    name: str
    status: str
    value: float | None
    detail: str

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "value": self.value,
            "detail": self.detail,
        }


def _band(
    name: str, value: float | None, warn_at: float, fail_at: float, detail: str
) -> MonitorCheck:
    if value is None:
        return MonitorCheck(name, "warn", None, detail + " (no data)")
    if value <= warn_at:
        status = "pass"
    elif value <= fail_at:
        status = "warn"
    else:
        status = "fail"
    return MonitorCheck(name, status, round(value, 2), detail)


def pipeline_lag_check(hours: float | None) -> MonitorCheck:
    detail = f"{hours:.1f}h since last article" if hours is not None else "no articles"
    return _band("pipeline_lag", hours, 24.0, 72.0, detail)


def backlog_check(n_pending: int) -> MonitorCheck:
    return _band("classify_backlog", float(n_pending), 50.0, 200.0, f"{n_pending} pending")


def unprocessed_check(name: str, count: int) -> MonitorCheck:
    return _band(name, float(count), 20.0, 100.0, f"{count} unprocessed")


def error_rate_check(n_failed: int, n_total: int) -> MonitorCheck:
    if n_total <= 0:
        return MonitorCheck("error_rate", "warn", None, "no job runs yet")
    rate = n_failed / n_total
    check = _band("error_rate", rate, 0.2, 0.5, f"{n_failed}/{n_total} failed")
    return MonitorCheck(check.name, check.status, round(rate, 4), check.detail)


def active_alerts_info(count: int) -> MonitorCheck:
    return MonitorCheck("active_alerts", "pass", float(count), f"{count} active")


def db_check(ok: bool) -> MonitorCheck:
    return MonitorCheck(
        "database", "pass" if ok else "fail", 1.0 if ok else 0.0,
        "connected" if ok else "unreachable",
    )


def overall_status(checks: list[MonitorCheck]) -> str:
    if not checks:
        return "fail"
    worst = max(SEVERITY_RANK[c.status] for c in checks)
    return next(k for k, v in SEVERITY_RANK.items() if v == worst)


__all__ = [
    "MonitorCheck",
    "active_alerts_info",
    "backlog_check",
    "db_check",
    "error_rate_check",
    "overall_status",
    "pipeline_lag_check",
    "unprocessed_check",
]
