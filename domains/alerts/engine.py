"""Alert Engine — ارزیابی قواعد و ثبت هشدار (Phase 43).

- هر قاعده‌ی فعال ارزیابی می‌شود؛ نقض + نبود هشدار active در پنجره‌ی
  cooldown همان قاعده → رکورد Alert جدید.
- cooldown از observed_at آخرین هشدار همان قاعده سنجیده می‌شود.
- تأیید/حل دستی وضعیت را عوض می‌کند (رکورد حذف نمی‌شود).
- بدون AI؛ تحویل خارجی در v1 نیست.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.alert import Alert, AlertRule
from domains.alerts.metrics import breached, resolve_metric

logger = get_logger(__name__)

VALID_OPERATORS = ("gt", "lt")


@dataclass
class AlertOutcome:
    evaluated: int = 0
    triggered: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "evaluated": self.evaluated,
            "triggered": self.triggered,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
        }


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class AlertEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _in_cooldown(self, rule: AlertRule, now: datetime) -> bool:
        last = self.db.execute(
            select(Alert)
            .where(Alert.rule_id == rule.id, Alert.status == "active")
            .order_by(Alert.observed_at.desc())
            .limit(1)
        ).scalars().first()
        if last is None:
            return False
        seen = _aware(last.observed_at)
        if seen is None:
            return False
        return now - seen < timedelta(hours=rule.cooldown_hours or 0)

    def evaluate(self) -> AlertOutcome:
        outcome = AlertOutcome()
        now = datetime.now(UTC)
        rules = list(
            self.db.execute(
                select(AlertRule).where(AlertRule.active.is_(True)).order_by(AlertRule.name)
            )
            .scalars()
            .all()
        )
        for rule in rules:
            try:
                outcome.evaluated += 1
                if rule.operator not in VALID_OPERATORS:
                    outcome.failed += 1
                    outcome.errors.append(f"rule {rule.name}: bad operator")
                    continue
                value = resolve_metric(self.db, rule.metric)
                if value is None:
                    outcome.skipped += 1
                    continue
                if not breached(value, rule.operator, rule.threshold):
                    continue
                if self._in_cooldown(rule, now):
                    outcome.skipped += 1
                    continue
                self.db.add(
                    Alert(
                        rule_id=rule.id,
                        metric=rule.metric,
                        value=value,
                        message=(
                            f"{rule.metric} {rule.operator} {rule.threshold} "
                            f"(now {round(value, 4)})"
                        ),
                        severity=rule.severity or "warning",
                        status="active",
                        observed_at=now,
                    )
                )
                self.db.flush()
                outcome.triggered += 1
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("alert evaluate failed | rule=%s err=%s", rule.id, exc)
        self.db.commit()
        logger.info("alerts evaluated | %s", outcome.as_dict())
        return outcome

    def acknowledge(self, alert_id: object) -> Alert | None:
        alert = self.db.get(Alert, alert_id)
        if alert is None:
            return None
        if alert.status == "active":
            alert.status = "acknowledged"
            self.db.commit()
        return alert

    def resolve(self, alert_id: object) -> Alert | None:
        alert = self.db.get(Alert, alert_id)
        if alert is None:
            return None
        if alert.status in ("active", "acknowledged"):
            alert.status = "resolved"
            self.db.commit()
        return alert
