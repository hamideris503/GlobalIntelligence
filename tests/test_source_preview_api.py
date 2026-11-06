"""UX-01 — پیش‌نمایش منبع باید بدون ingest باشد.

قبل از این مسیر، دکمه‌ی «دریافت آزمایشی» در UI مستقیم `POST /api/ingest` می‌زد و
داده ذخیره می‌کرد. این تست‌ها اثبات می‌کنند مسیر جدید هیچ ردیفی نمی‌سازد.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.database.models.document import Document
from backend.database.models.source import Source
from tests.conftest import TestingSession


def _source(**over: object) -> str:
    session = TestingSession()
    try:
        data = {
            "name": "PreviewSrc",
            "domain": "preview.local",
            "type": "rss",
            "collection_method": "rss",
            "feed_url": "https://example.com/feed.xml",
            "active": True,
        }
        data.update(over)
        src = Source(**data)
        session.add(src)
        session.commit()
        return str(src.id)
    finally:
        session.close()


def _document_count() -> int:
    session = TestingSession()
    try:
        return session.query(Document).count()
    finally:
        session.close()


def test_preview_never_ingests(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    sid = _source()
    before = _document_count()

    def _fake(adapter: str, url: str | None, limit: int = 5) -> dict:
        return {
            "adapter": adapter,
            "url_origin": "https://example.com",
            "count": 2,
            "samples": [
                {"title": "sample one", "summary": None, "content_chars": 4,
                 "content_sha256": "aaa", "published_at": None},
                {"title": "sample two", "summary": None, "content_chars": 5,
                 "content_sha256": "bbb", "published_at": None},
            ],
            "ingested": False,
        }

    monkeypatch.setattr("backend.configuration.preview.preview_fetch", _fake)
    resp = client.post(f"/api/sources/{sid}/preview?limit=5")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ingested"] is False
    assert body["count"] == 2
    assert body["adapter"] == "rss"
    assert body["source_name"] == "PreviewSrc"
    assert body["config_revision"] is None
    assert _document_count() == before  # هیچ سندی ذخیره نشد


def test_preview_uses_pinned_configuration_revision(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from backend.database.models.configuration import (
        ConfigurationInstance,
        ConfigurationRevision,
    )

    sid = _source(name="PinnedPreviewSrc")
    session = TestingSession()
    try:
        inst = ConfigurationInstance(
            kind="source", slug="PinnedPreviewSrc", latest_revision=1, active_revision=1
        )
        session.add(inst)
        session.flush()
        session.add(
            ConfigurationRevision(
                instance_id=inst.id, revision_number=1, status="active",
                payload_json=json.dumps({
                    "name": "PinnedPreviewSrc", "type": "rss",
                    "collection_method": "rss",
                    "feed_url": "https://pinned.example.com/feed.xml",
                }),
            )
        )
        session.commit()
    finally:
        session.close()

    seen: list[str | None] = []

    def _fake(adapter: str, url: str | None, limit: int = 5) -> dict:
        seen.append(url)
        return {"adapter": adapter, "url_origin": "https://pinned.example.com",
                "count": 0, "samples": [], "ingested": False}

    monkeypatch.setattr("backend.configuration.preview.preview_fetch", _fake)
    body = client.post(f"/api/sources/{sid}/preview").json()
    assert body["config_revision"] == 1
    assert seen == ["https://pinned.example.com/feed.xml"]


def test_preview_rejects_source_without_endpoint(client: TestClient) -> None:
    sid = _source(name="NoEndpointSrc", feed_url=None)
    resp = client.post(f"/api/sources/{sid}/preview")
    assert resp.status_code == 422
    assert "skip" in resp.json()["detail"]


def test_preview_reports_unsupported_adapter(client: TestClient) -> None:
    sid = _source(
        name="CsvPreviewSrc", collection_method="dataset", type="dataset",
        feed_url=None, data_download_url="https://example.com/data.csv",
    )
    resp = client.post(f"/api/sources/{sid}/preview")
    assert resp.status_code == 422
    assert "preview is not supported" in resp.json()["detail"]


def test_preview_unknown_source_is_404(client: TestClient) -> None:
    assert client.post(f"/api/sources/{uuid.uuid4()}/preview").status_code == 404
