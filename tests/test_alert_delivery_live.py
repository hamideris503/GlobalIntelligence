"""Live alert delivery tests (F12) — network mocked."""
from __future__ import annotations

import uuid

from backend.database.models.alert import Alert, AlertRule
from domains.alerts import delivery as D
from tests.conftest import TestingSession


def _seed(session):
    rule = AlertRule(name="r-" + uuid.uuid4().hex[:6], metric="risk:x", operator="gt", threshold=0.5, active=True)
    session.add(rule)
    session.flush()
    alert = Alert(rule_id=rule.id, metric="risk:x", value=0.9, message="m", severity="warning", status="active")
    session.add(alert)
    session.commit()
    return alert


def test_telegram_live_success(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setattr(D, "_http_post_json", lambda url, payload, timeout=10: (200, '{"ok":true}'))
    session = TestingSession()
    try:
        alert = _seed(session)
        d = D.deliver_alert(session, alert, "telegram", dry_run=False)
        assert d.status == "sent"
        assert d.last_error is None
    finally:
        session.close()


def test_telegram_live_failure(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setattr(D, "_http_post_json", lambda url, payload, timeout=10: (400, '{"ok":false,"description":"bad"}'))
    session = TestingSession()
    try:
        alert = _seed(session)
        d = D.deliver_alert(session, alert, "telegram", dry_run=False)
        assert d.status == "failed"
        assert "telegram http 400" in (d.last_error or "")
    finally:
        session.close()


def test_email_live_success(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_TO", "a@b.com")
    monkeypatch.setenv("SMTP_FROM", "from@b.com")
    monkeypatch.setattr(D, "_smtp_send", lambda **kw: None)
    session = TestingSession()
    try:
        alert = _seed(session)
        d = D.deliver_alert(session, alert, "email", dry_run=False)
        assert d.status == "sent"
    finally:
        session.close()


def test_email_live_failure(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_TO", "a@b.com")
    monkeypatch.setenv("SMTP_FROM", "from@b.com")

    def boom(**kw):
        raise RuntimeError("conn refused")

    monkeypatch.setattr(D, "_smtp_send", boom)
    session = TestingSession()
    try:
        alert = _seed(session)
        d = D.deliver_alert(session, alert, "email", dry_run=False)
        assert d.status == "failed"
        assert "email error" in (d.last_error or "")
    finally:
        session.close()


def test_missing_creds_skipped(monkeypatch):
    # ensure no creds
    for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "SMTP_HOST", "SMTP_TO"):
        monkeypatch.delenv(k, raising=False)
    session = TestingSession()
    try:
        alert = _seed(session)
        d = D.deliver_alert(session, alert, "telegram", dry_run=False)
        assert d.status == "skipped"
    finally:
        session.close()


def test_idempotent_sent_not_resend(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    calls = {"n": 0}

    def fake(url, payload, timeout=10):
        calls["n"] += 1
        return 200, '{"ok":true}'

    monkeypatch.setattr(D, "_http_post_json", fake)
    session = TestingSession()
    try:
        alert = _seed(session)
        d1 = D.deliver_alert(session, alert, "telegram", dry_run=False)
        assert d1.status == "sent"
        d2 = D.deliver_alert(session, alert, "telegram", dry_run=False)
        assert d2.id == d1.id
        assert calls["n"] == 1  # not re-sent
    finally:
        session.close()


def test_max_attempts_terminal(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123")
    monkeypatch.setattr(D, "_http_post_json", lambda url, payload, timeout=10: (500, ""))
    session = TestingSession()
    try:
        alert = _seed(session)
        # exhaust attempts
        for _ in range(D.MAX_ATTEMPTS):
            D.deliver_alert(session, alert, "telegram", dry_run=False)
        d = D.deliver_alert(session, alert, "telegram", dry_run=False)
        assert d.status == "failed"
        assert d.last_error == "max attempts reached" or "max" in (d.last_error or "")
    finally:
        session.close()
