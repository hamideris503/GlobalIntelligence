"""مرحله ۳: `GET /api/geo/events` و نگاشت دسته‌ها.

قاعدهٔ مرکزی: هیچ مختصاتی ساخته نمی‌شود؛ رویداد بدون lat/lon برنمی‌گردد و
فقط در `metadata.without_location` شمرده می‌شود.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.auth.deps import CurrentUser, require_user
from backend.core.config import get_settings
from backend.database.models.event import Event
from backend.main import app
from domains.geo.category_map import category_for
from tests.conftest import TestingSession


def _event(**kwargs) -> Event:
    now = datetime.now(UTC)
    data = {
        "event_type": "attack",
        "occurred_at": now,
        "retrieved_at": now,
        "available_at": now,
        "observed_at": now,
    }
    data.update(kwargs)
    return Event(**data)


def _seed(*events: Event) -> None:
    session = TestingSession()
    try:
        session.add_all(events)
        session.commit()
    finally:
        session.close()


def test_feature_collection_structure_and_no_fabrication(client: TestClient) -> None:
    located = _event(
        event_type="attack",
        action="حملهٔ آزمایشی",
        occurred_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
        latitude=35.6892,
        longitude=51.3890,
        country="IR",
        location="تهران",
        location_precision="city",
        location_source="gazetteer",
        location_confidence=0.9,
        confidence=0.7,
        sources=json.dumps(["src-1", "src-2"]),
    )
    missing = _event(event_type="attack")  # location textual but no coordinates
    unknown = _event(event_type="unmapped-event-kind", latitude=10.0, longitude=20.0)
    _seed(located, missing, unknown)

    res = client.get("/api/geo/events")
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 1
    feature = body["features"][0]
    assert feature["type"] == "Feature"
    assert feature["geometry"] == {"type": "Point", "coordinates": [51.389, 35.6892]}
    props = feature["properties"]
    assert props["id"] == str(located.id)
    assert props["category"] == "attacks"
    assert props["type"] == "attack"
    assert props["title"] == "حملهٔ آزمایشی"
    assert props["source"] == ["src-1", "src-2"]
    assert props["location_precision"] == "city"
    assert props["location_source"] == "gazetteer"
    assert body["metadata"]["without_location"] == 1
    assert body["metadata"]["total"] == 1
    assert body["metadata"]["returned"] == 1
    assert body["metadata"]["truncated"] is False


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ({"country": "IR"}, 1),
        ({"country": "US"}, 1),
        ({"country": "CN"}, 0),
        ({"category": "protests"}, 1),
        ({"category": "attacks"}, 1),
        ({"category": "sanctions"}, 0),
        ({"min_confidence": 0.5}, 1),
        ({"min_confidence": 0.95}, 0),
        # تهران داخل این کادر است
        ({"bbox": "50,30,55,40"}, 1),
        ({"bbox": "-10,30,10,40"}, 0),
    ],
)
def test_filters(client: TestClient, query: dict, expected: int) -> None:
    _seed(
        _event(
            event_type="attack",
            occurred_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC),
            latitude=35.6892,
            longitude=51.3890,
            country="IR",
            confidence=0.8,
        ),
        _event(
            event_type="protest",
            occurred_at=datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
            latitude=40.0,
            longitude=-100.0,
            country="US",
            confidence=0.4,
        ),
    )
    body = client.get("/api/geo/events", params=query).json()
    assert len(body["features"]) == expected


def test_time_range_filter(client: TestClient) -> None:
    _seed(
        _event(
            event_type="conflict",
            occurred_at=datetime(2026, 10, 1, tzinfo=UTC),
            latitude=10.0,
            longitude=10.0,
        ),
        _event(
            event_type="conflict",
            occurred_at=datetime(2026, 11, 1, tzinfo=UTC),
            latitude=20.0,
            longitude=20.0,
        ),
    )
    body = client.get(
        "/api/geo/events", params={"since": "2026-10-15T00:00:00Z"}
    ).json()
    assert len(body["features"]) == 1
    assert body["features"][0]["geometry"]["coordinates"] == [20.0, 20.0]


def test_limit_and_truncated(client: TestClient) -> None:
    _seed(*[
        _event(
            event_type="military",
            occurred_at=datetime(2026, 11, 1, 12, 0, tzinfo=UTC) + timedelta(hours=i),
            latitude=float(i),
            longitude=float(i),
        )
        for i in range(3)
    ])
    body = client.get("/api/geo/events", params={"limit": 2}).json()
    assert len(body["features"]) == 2
    assert body["metadata"]["total"] == 3
    assert body["metadata"]["returned"] == 2
    assert body["metadata"]["truncated"] is True


def test_invalid_bbox_uses_stage2_envelope(client: TestClient) -> None:
    res = client.get("/api/geo/events", params={"bbox": "1,2,3"})
    assert res.status_code == 422
    body = res.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "bbox" in body["error"]["details"]["fields"]
    assert body["detail"] == body["error"]["message"]
    assert res.headers.get("X-Request-ID")

    res = client.get("/api/geo/events", params={"bbox": "10,40,0,30"})
    assert res.status_code == 422
    assert "bbox" in res.json()["error"]["details"]["fields"]


def test_unknown_category_is_rejected(client: TestClient) -> None:
    res = client.get("/api/geo/events", params={"category": "not-a-layer"})
    assert res.status_code == 422
    assert "category" in res.json()["error"]["details"]["fields"]


def test_etag_returns_304(client: TestClient) -> None:
    _seed(_event(latitude=1.0, longitude=2.0))
    first = client.get("/api/geo/events")
    etag = first.headers["ETag"]
    second = client.get("/api/geo/events", headers={"If-None-Match": etag})
    assert second.status_code == 304


def test_viewer_can_read_and_anonymous_is_rejected(
    client: TestClient, monkeypatch
) -> None:
    app.dependency_overrides[require_user] = lambda: CurrentUser(
        username="viewer", role="viewer", via="session"
    )
    try:
        assert client.get("/api/geo/events").status_code == 200
    finally:
        app.dependency_overrides.pop(require_user, None)

    monkeypatch.setenv("API_KEY", "test-key-123")
    get_settings.cache_clear()
    anonymous = TestClient(app, raise_server_exceptions=False)
    assert anonymous.get("/api/geo/events").status_code == 401
    assert anonymous.get(
        "/api/geo/events", headers={"X-API-Key": "test-key-123"}
    ).status_code == 200


def test_category_map_is_explicit_and_unknown_is_dropped() -> None:
    assert category_for("ATTACK") == "attacks"
    assert category_for("armed-conflict") == "conflict"
    assert category_for("Cyber_Attack") == "cyber"
    assert category_for("unknown") is None
    assert category_for(None) is None
