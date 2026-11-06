"""فیلتر precision در /api/geo/events."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.database.models.event import Event
from tests.conftest import TestingSession


def _ev(precision: str, lat: float, lon: float) -> Event:
    now = datetime.now(UTC)
    return Event(
        event_type="conflict",
        occurred_at=now,
        latitude=lat,
        longitude=lon,
        country="IR",
        location_precision=precision,
        location_source="test",
    )


def test_precision_filter(client: TestClient) -> None:
    s = TestingSession()
    s.add_all([_ev("city", 35.0, 51.0), _ev("country", 32.0, 53.0)])
    s.commit()
    s.close()
    body = client.get("/api/geo/events", params={"precision": "city"}).json()
    assert len(body["features"]) == 1
    assert body["features"][0]["properties"]["location_precision"] == "city"
    body2 = client.get("/api/geo/events", params={"precision": "country"}).json()
    assert len(body2["features"]) == 1
    assert body2["features"][0]["properties"]["location_precision"] == "country"


def test_precision_invalid_rejected(client: TestClient) -> None:
    res = client.get("/api/geo/events", params={"precision": "region"})
    assert res.status_code == 422
    assert "precision" in res.json()["error"]["details"]["fields"]
