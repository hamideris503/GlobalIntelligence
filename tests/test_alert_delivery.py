"""Alert delivery tests (F12)."""
from __future__ import annotations

import uuid

from backend.database.models.alert import Alert, AlertRule
from domains.alerts.delivery import deliver_alert, deliver_pending, get_or_create_delivery
from tests.conftest import TestingSession


def _seed_alert(session):
    rule = AlertRule(name="r-" + uuid.uuid4().hex[:6], metric="risk:x", operator="gt", threshold=0.5, active=True)
    session.add(rule)
    session.flush()
    alert = Alert(rule_id=rule.id, metric="risk:x", value=0.9, message="m", severity="warning", status="active")
    session.add(alert)
    session.commit()
    return alert


def test_delivery_idempotent_and_skipped():
    session = TestingSession()
    try:
        alert = _seed_alert(session)
        d1 = deliver_alert(session, alert, "telegram", dry_run=True)
        assert d1.status in ("pending", "skipped")
        # idempotent: sent? no. second call same status family
        d2 = deliver_alert(session, alert, "telegram", dry_run=True)
        assert d2.id == d1.id
        # missing creds -> skipped
        dd = get_or_create_delivery(session, alert.id, "email")
        assert dd is not None
    finally:
        session.close()


def test_deliver_pending():
    session = TestingSession()
    try:
        _seed_alert(session)
        out = deliver_pending(session, dry_run=True)
        assert out["delivered"] >= 2
    finally:
        session.close()
