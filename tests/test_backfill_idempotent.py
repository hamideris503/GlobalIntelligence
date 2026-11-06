"""Idempotency of the deterministic backfill."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from backend.database.models.event import Event
from scripts.backfill_event_geo import run_session
from tests.conftest import TestingSession


def test_backfill_is_idempotent() -> None:
    session = TestingSession()
    now = datetime.now(UTC)
    session.add(Event(
        event_type="unknown",
        action="Federal Reserve raises interest rates as inflation surges; markets fall",
        occurred_at=now,
        published_at=now, retrieved_at=now, available_at=now, observed_at=now,
    ))
    session.commit()

    first = run_session(session, apply=True, limit=None)
    assert first["type_assigned"] == 1
    assert first["geo_unresolved"] == 1  # no location in text

    # second run: nothing to fill
    second = run_session(session, apply=True, limit=None)
    assert second["type_assigned"] == 0
    assert second["geo_city"] == 0 and second["geo_country"] == 0

    # verify persisted
    ev = session.execute(select(Event)).scalars().one()
    assert ev.event_type == "economic"
    session.close()
