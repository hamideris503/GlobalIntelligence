"""قیف دریافت `/api/ingest/stats` (مرحلهٔ ۴)."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.auth.deps import CurrentUser, require_user
from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from backend.main import app
from tests.conftest import TestingSession


def _seed() -> None:
    s = TestingSession()
    src = Source(name="funnel", type="rss", active=True)
    s.add(src)
    s.flush()
    now = datetime.now(UTC)
    doc = Document(
        source_id=src.id, url="https://example.com/f", title="t",
        content_hash="hash-1", duplicate_status="new", priority_status="RULES_ONLY",
        retrieved_at=now,
    )
    s.add(doc)
    s.flush()
    s.add(Article(document_id=doc.id, title="a", classification_status="done",
                  retrieved_at=now, observed_at=now))
    s.commit()
    s.close()


def test_stats_default_window_shape(client: TestClient) -> None:
    body = client.get("/api/ingest/stats").json()
    assert body["window"] == "24h"
    assert set(body["stages"]) == {
        "fetched", "normalized", "dedup", "prioritized", "classified", "analyzed", "stored",
    }
    assert "uncomputed" in body


def test_stats_counts_real_rows(client: TestClient) -> None:
    _seed()
    body = client.get("/api/ingest/stats?window=24h").json()
    assert body["stages"]["fetched"] >= 1
    assert body["stages"]["normalized"] >= 1
    assert body["stages"]["prioritized"] >= 1
    assert body["stages"]["classified"] >= 1


def test_stats_7d_window(client: TestClient) -> None:
    body = client.get("/api/ingest/stats?window=7d").json()
    assert body["window"] == "7d"


def test_stats_invalid_window_envelope(client: TestClient) -> None:
    res = client.get("/api/ingest/stats?window=1y")
    assert res.status_code == 422
    body = res.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "window" in body["error"]["details"]["fields"]
    assert body["detail"] == body["error"]["message"]


def test_stats_empty_returns_zero_not_error(client: TestClient) -> None:
    body = client.get("/api/ingest/stats?window=24h").json()
    # with no rows in window the computed stages are 0 (not null)
    assert body["stages"]["fetched"] == 0
    assert body["uncomputed"] == []


def test_stats_viewer_allowed(client: TestClient) -> None:
    app.dependency_overrides[require_user] = lambda: CurrentUser(
        username="v", role="viewer", via="session"
    )
    try:
        assert client.get("/api/ingest/stats").status_code == 200
    finally:
        app.dependency_overrides.pop(require_user, None)
