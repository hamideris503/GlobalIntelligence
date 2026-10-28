"""Monitoring service — گردآوری وضعیت مانیتورینگ + متریک‌های Prometheus (Phase 50).

بدون migration؛ فقط خواندنی.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.ai.local_screening import get_screening_stats
from backend.core.logging import get_logger
from backend.database.models.alert import Alert
from backend.database.models.article import Article
from backend.database.models.claim import Claim
from backend.database.models.event import Event
from backend.database.models.job import JobRun
from backend.database.models.market import MarketObservation
from domains.markets.fetchers import SYMBOLS
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

    def _count(self, model: object, *filters) -> int | None:  # type: ignore[valid-type]
        # AUDIT-REPAIR: خطای query تهی/منفی جعلی نیست؛ None یعنی «نامشخص» و fail می‌شود
        stmt = select(func.count()).select_from(model)
        for f in filters:
            stmt = stmt.where(f)
        try:
            return int(self.db.execute(stmt).scalars().one() or 0)
        except Exception:  # noqa: BLE001
            return None

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
            mon.count_check(
                "classify_backlog",
                self._count(Article, Article.classification_status == "pending"),
                50.0, 200.0, "pending classification",
            )
        )
        checks.append(
            mon.count_check(
                "unprocessed_events",
                self._count(Event, Event.claims_extracted.is_(False)),
                20.0, 100.0, "unprocessed events",
            )
        )
        checks.append(
            mon.count_check(
                "unprocessed_claims",
                self._count(Claim, Claim.evidence_extracted.is_(False)),
                20.0, 100.0, "unprocessed claims",
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

        # قدمت قیمت هر نماد: جدیدترین مشاهده‌ی هر نماد کاتالوگ، بدترین قدمت.
        try:
            latest_rows = self.db.execute(
                select(
                    MarketObservation.symbol,
                    func.max(MarketObservation.observed_at),
                ).group_by(MarketObservation.symbol)
            ).all()
            latest_by_symbol = {symbol: _aware(ts) for symbol, ts in latest_rows}
            ages = [
                ((now - latest_by_symbol[s]).total_seconds() / 3600.0, s)
                for s in SYMBOLS
                if latest_by_symbol.get(s) is not None
            ]
            if ages:
                worst_age, worst_symbol = max(ages)
                checks.append(mon.market_staleness_check(worst_age, worst_symbol))
            else:
                checks.append(mon.market_staleness_check(None))
        except Exception:  # noqa: BLE001
            checks.append(
                mon.MonitorCheck(
                    "market_staleness", "fail", None, "staleness query failed"
                )
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

        screening = get_screening_stats().as_dict()
        lines.extend([
            "# HELP gi_local_screening_screens_total actual advisory screening runs",
            "# TYPE gi_local_screening_screens_total counter",
            f"gi_local_screening_screens_total {screening['screens']}",
            "# HELP gi_local_screening_skipped_total screening runs skipped before inference",
            "# TYPE gi_local_screening_skipped_total counter",
            f"gi_local_screening_skipped_total {screening['skipped']}",
            "# HELP gi_local_screening_calls_total provider requests attempted",
            "# TYPE gi_local_screening_calls_total counter",
            f"gi_local_screening_calls_total {screening['calls']}",
            "# HELP gi_local_screening_success_total valid provider responses",
            "# TYPE gi_local_screening_success_total counter",
            f"gi_local_screening_success_total {screening['success']}",
            "# HELP gi_local_screening_errors_total provider requests that failed",
            "# TYPE gi_local_screening_errors_total counter",
            f"gi_local_screening_errors_total {screening['errors']}",
            "# HELP gi_local_screening_timeouts_total provider request timeouts",
            "# TYPE gi_local_screening_timeouts_total counter",
            f"gi_local_screening_timeouts_total {screening['timeouts']}",
            "# HELP gi_local_screening_connection_errors_total provider connection failures",
            "# TYPE gi_local_screening_connection_errors_total counter",
            "gi_local_screening_connection_errors_total "
            f"{screening['connection_errors']}",
            "# HELP gi_local_screening_invalid_total rejected provider outputs",
            "# TYPE gi_local_screening_invalid_total counter",
            f"gi_local_screening_invalid_total {screening['invalid']}",
            "# HELP gi_local_screening_unavailable_total unavailable provider attempts",
            "# TYPE gi_local_screening_unavailable_total counter",
            f"gi_local_screening_unavailable_total {screening['unavailable']}",
            "# HELP gi_local_screening_decided_total advisory decisions",
            "# TYPE gi_local_screening_decided_total counter",
            f"gi_local_screening_decided_total {screening['decided']}",
            "# HELP gi_local_screening_abstained_total advisory abstentions",
            "# TYPE gi_local_screening_abstained_total counter",
            f"gi_local_screening_abstained_total {screening['abstained']}",
            "# HELP gi_local_screening_latency_ms_total provider latency sum",
            "# TYPE gi_local_screening_latency_ms_total counter",
            "gi_local_screening_latency_ms_total "
            f"{screening['total_latency_ms']}",
        ])
        if screening["avg_latency_ms"] is not None:
            lines.extend([
                "# HELP gi_local_screening_latency_ms_avg mean provider latency",
                "# TYPE gi_local_screening_latency_ms_avg gauge",
                "gi_local_screening_latency_ms_avg "
                f"{screening['avg_latency_ms']}",
            ])

        provider_metrics = [
            ("calls", "calls", "counter", "provider requests"),
            ("success", "success", "counter", "valid responses"),
            ("errors", "errors", "counter", "failed requests"),
            ("timeouts", "timeouts", "counter", "request timeouts"),
            ("connection_errors", "connection_errors", "counter", "connection failures"),
            ("invalid", "invalid", "counter", "rejected outputs"),
            ("unavailable", "unavailable", "counter", "unavailable attempts"),
            ("decided", "decided", "counter", "advisory decisions"),
            ("abstained", "abstained", "counter", "abstentions"),
            ("latency_ms_total", "total_latency_ms", "counter", "latency sum"),
        ]
        for suffix, key, kind, help_text in provider_metrics:
            name = f"gi_local_screening_provider_{suffix}"
            if kind == "counter" and not name.endswith("_total"):
                name += "_total"
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} {kind}")
            for provider, item in screening["providers"].items():
                label = str(provider).replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{name}{{provider="{label}"}} {item[key]}')
        lines.extend([
            "# HELP gi_local_screening_provider_latency_ms_avg mean provider latency",
            "# TYPE gi_local_screening_provider_latency_ms_avg gauge",
        ])
        for provider, item in screening["providers"].items():
            if item["avg_latency_ms"] is None:
                continue
            label = str(provider).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(
                "gi_local_screening_provider_latency_ms_avg"
                f'{{provider="{label}"}} {item["avg_latency_ms"]}'
            )
        return "\n".join(lines) + "\n"


__all__ = ["MonitoringOutcome", "MonitoringService"]
