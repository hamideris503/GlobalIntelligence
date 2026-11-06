"""Alert delivery layer (F12). Dry-run safe; live send only with credentials.

Network I/O is isolated in ``_http_post_json`` / ``_smtp_send`` so tests can
replace them without touching real services. Secrets are read from env and never
logged or returned.
"""
from __future__ import annotations

import json
import os
import smtplib
import ssl
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.alert import Alert
from backend.database.models.alert_delivery import AlertDelivery

logger = get_logger(__name__)

MAX_ATTEMPTS = 3
RETRY_DELAYS = (0.05, 0.1)


def _env(name: str) -> str | None:
    v = os.getenv(name)
    return v.strip() if v else None


def _channel_enabled(channel: str) -> bool:
    if channel == "telegram":
        return bool(_env("TELEGRAM_BOT_TOKEN") and _env("TELEGRAM_CHAT_ID"))
    if channel == "email":
        return bool(_env("SMTP_HOST") and _env("SMTP_TO"))
    return False


def _http_post_json(url: str, payload: dict[str, Any], timeout: int = 10) -> tuple[int, str]:
    """POST JSON. Returns (status_code, body_text). Raises on network error."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        return int(e.code), body


def _smtp_send(
    host: str,
    port: int,
    username: str | None,
    password: str | None,
    use_tls: bool,
    sender: str,
    recipients: list[str],
    subject: str,
    body: str,
    timeout: int = 10,
) -> None:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(body)
    if use_tls:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as server:
            if username and password:
                server.login(username, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=timeout) as server:
            server.starttls(context=ssl.create_default_context())
            if username and password:
                server.login(username, password)
            server.send_message(msg)


def _retry(call: Callable[[], tuple[bool, str | None]]) -> tuple[bool, str | None]:
    last: tuple[bool, str | None] = (False, "not attempted")
    for i, delay in enumerate((0.0,) + RETRY_DELAYS):
        if i > 0:
            time.sleep(delay)
        ok, err = call()
        last = (ok, err)
        if ok:
            return last
        # retry on transient (network-ish) errors; hard HTTP 4xx/5xx are terminal
        if err and err.startswith("telegram http 4"):
            return last
    return last


def _send_telegram(alert: Alert) -> tuple[bool, str | None]:
    token = _env("TELEGRAM_BOT_TOKEN")
    chat_id = _env("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False, "missing credentials"
    url = f"https://api.telegram.org/bot{token}/sendMessage"

    def _once() -> tuple[bool, str | None]:
        payload = {
            "chat_id": chat_id,
            "text": f"[{alert.severity or 'info'}] {alert.message or ''}".strip(),
            "disable_web_page_preview": True,
        }
        try:
            status, body = _http_post_json(url, payload)
        except Exception as exc:  # network/timeout
            return False, f"telegram network error: {type(exc).__name__}"
        if 200 <= status < 300:
            try:
                j = json.loads(body)
                if j.get("ok") is True:
                    return True, None
                return False, str(j.get("description") or "telegram api error")
            except (ValueError, TypeError):
                return True, None
        return False, f"telegram http {status}"

    return _retry(_once)


def _send_email(alert: Alert) -> tuple[bool, str | None]:
    host = _env("SMTP_HOST")
    port_raw = _env("SMTP_PORT") or "587"
    sender = _env("SMTP_FROM") or _env("SMTP_TO")
    recipients_raw = _env("SMTP_TO") or ""
    username = _env("SMTP_USER")
    password = _env("SMTP_PASSWORD")
    use_tls = (_env("SMTP_USE_TLS") or "true").lower() not in {"0", "false", "no"}
    if not host or not recipients_raw or not sender:
        return False, "missing credentials"
    try:
        port = int(port_raw)
    except ValueError:
        return False, "invalid SMTP_PORT"

    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    subject = f"[{alert.severity or 'info'}] Alert: {alert.metric}"
    body = (
        f"Metric: {alert.metric}\n"
        f"Value: {alert.value}\n"
        f"Severity: {alert.severity}\n"
        f"Message: {alert.message}\n"
        f"Observed: {alert.observed_at}\n"
    )

    def _once() -> tuple[bool, str | None]:
        try:
            _smtp_send(
                host=host,
                port=port,
                username=username,
                password=password,
                use_tls=use_tls,
                sender=sender,
                recipients=recipients,
                subject=subject,
                body=body,
            )
            return True, None
        except Exception as exc:
            return False, f"email error: {type(exc).__name__}"

    return _retry(_once)


def get_or_create_delivery(db: Session, alert_id: uuid.UUID, channel: str) -> AlertDelivery:
    row = db.execute(
        select(AlertDelivery).where(AlertDelivery.alert_id == alert_id, AlertDelivery.channel == channel)
    ).scalars().first()
    if row is not None:
        return row
    row = AlertDelivery(
        alert_id=alert_id,
        channel=channel,
        status="pending",
        idempotency_key=f"{alert_id}:{channel}",
    )
    db.add(row)
    db.flush()
    return row


def deliver_alert(db: Session, alert: Alert, channel: str, *, dry_run: bool = True) -> AlertDelivery:
    delivery = get_or_create_delivery(db, alert.id, channel)
    if delivery.status == "sent":
        return delivery  # idempotent
    if delivery.attempts >= MAX_ATTEMPTS:
        delivery.status = "failed"
        delivery.last_error = "max attempts reached"
        db.commit()
        return delivery
    if not _channel_enabled(channel):
        delivery.status = "skipped"
        delivery.last_error = "missing credentials"
        delivery.attempts += 1
        db.commit()
        return delivery
    if dry_run:
        delivery.status = "pending"
        delivery.last_error = "dry-run (no live send)"
        delivery.attempts += 1
        db.commit()
        return delivery
    # live send
    if channel == "telegram":
        ok, err = _send_telegram(alert)
    elif channel == "email":
        ok, err = _send_email(alert)
    else:
        ok, err = False, "unknown channel"
    delivery.attempts += 1
    if ok:
        delivery.status = "sent"
        delivery.delivered_at = datetime.now(UTC)
        delivery.last_error = None
    else:
        delivery.status = "failed"
        delivery.last_error = err
    db.commit()
    return delivery


def deliver_pending(db: Session, *, dry_run: bool = True) -> dict[str, Any]:
    alerts = db.execute(select(Alert).where(Alert.status == "active")).scalars().all()
    results = []
    for a in alerts:
        for ch in ("telegram", "email"):
            d = deliver_alert(db, a, ch, dry_run=dry_run)
            results.append({"alert_id": str(a.id), "channel": ch, "status": d.status})
    return {"delivered": len(results), "results": results}
