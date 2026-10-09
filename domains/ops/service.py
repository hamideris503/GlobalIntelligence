"""Monitoring service — گردآوری وضعیت مانیتورینگ + متریک‌های Prometheus (Phase 50).

بدون migration؛ فقط خواندنی.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.alert import Alert
from backend.database.models.article import Article
from backend.database.models.claim import Claim
from backend.database.models.event import Event
from backend.database.models.job import JobRun
from domains.ops import monitoring as mon

logger = get_logger(__name__)


@dataclass
class MonitoringOutcome:
    status: str = "fail"
    checks: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"status": self.status, "checks": self.checks}


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class MonitoringService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _count(self, model: object, *filters) -> int:  # type: ignore[valid-type]
        stmt = select(func.count()).select_from(model)
        for f in filters:
            stmt = stmt.where(f)
        try:
            return int(self.db.execute(stmt).scalars().one() or 0)
        except Exception:  # noqa: BLE001
            return -1

    def report(self) -> MonitoringOutcome:
        now = datetime.now(UTC)
        checks: list[mon.MonitorCheck] = []

        try:
            self.db.execute(select(1))
            checks.append(mon.db_check(True))
        except Exception:  # noqa: BLE001
            checks.append(mon.db_check(False))
            return MonitoringOutcome(status="fail", checks=[c.as_dict() for c in checks])

        latest_article = self.db.execute(
            select(func.max(Article.retrieved_at))
        ).scalars().one()
        latest_article = _aware(latest_article)
        lag = (
            (now - latest_article).total_seconds() / 3600.0
            if latest_article
            else None
        )
        checks.append(mon.pipeline_lag_check(lag))
        checks.append(
            mon.backlog_check(
                self._count(Article, Article.classification_status == "pending")
            )
        )
        checks.append(
            mon.unprocessed_check(
                "unprocessed_events",
                self._count(Event, Event.claims_extracted.is_(False)),
            )
        )
        checks.append(
            mon.unprocessed_check(
                "unprocessed_claims",
                self._count(Claim, Claim.evidence_extracted.is_(False)),
            )
        )

        recent_jobs = list(
            self.db.execute(
                select(JobRun).order_by(JobRun.started_at.desc()).limit(50)
            )
            .scalars()
            .all()
        )
        n_failed = sum(1 for j in recent_jobs if (j.status or "") == "failed")
        checks.append(mon.error_rate_check(n_failed, len(recent_jobs)))
        checks.append(
            mon.active_alerts_info(self._count(Alert, Alert.status == "active"))
        )

        status = mon.overall_status(checks)
        logger.info("monitoring report | status=%s", status)
        return MonitoringOutcome(
            status=status, checks=[c.as_dict() for c in checks]
        )

    def prometheus(self) -> str:
        """متریک‌های سبک به فرمت Prometheus exposition."""
        report = self.report()
        lines = [
            "# HELP gi_monitor_status mean check score (pass=1 warn=0.5 fail=0)",
            "# TYPE gi_monitor_status gauge",
        ]
        rank = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
        score = (
            sum(rank.get(c["status"], 0.0) for c in report.checks) / len(report.checks)
            if report.checks
            else 0.0
        )
        lines.append(f"gi_monitor_status {score:.4f}")
        lines.append("# HELP gi_monitor_check 1 if check passes else 0")
        lines.append("# TYPE gi_monitor_check gauge")
        for c in report.checks:
            name = "".join(ch if ch.isalnum() else "_" for ch in c["name"])
            passed = 1 if c["status"] == "pass" else 0
            lines.append(f'gi_monitor_check{{check="{name}"}} {passed}')
            if c["value"] is not None:
                lines.append(f'gi_monitor_value{{check="{name}"}} {c["value"]}')
        n_articles = self._count(Article)
        n_pending = self._count(Article, Article.classification_status == "pending")
        lines.append("# HELP gi_articles_total total articles")
        lines.append("# TYPE gi_articles_total gauge")
        lines.append(f"gi_articles_total {n_articles}")
        lines.append("# HELP gi_articles_pending pending classification")
        lines.append("# TYPE gi_articles_pending gauge")
        lines.append(f"gi_articles_pending {n_pending}")
        return "\n".join(lines) + "\n"


__all__ = ["MonitoringOutcome", "MonitoringService"]
