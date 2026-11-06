"""F03.0 — configuration control plane (descriptor, revisions, preview, rollback).

مسیر تست از API می‌گذرد تا wiring روتر در main هم پوشش داده شود.
preview شبکه‌ای با stub جایگزین می‌شود؛ سیاست SSRF جداگانه و بدون شبکه سنجیده می‌شود.
"""
from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.configuration import preview as preview_mod
from source_bot.registry import ADAPTERS, PREVIEW_ADAPTERS
from source_bot.security import UrlCheck, validate_url

BASE = "/api/configuration"


def _payload(**over: object) -> dict:
    base: dict = {
        "name": "cfg-source",
        "type": "rss",
        "collection_method": "rss",
        "feed_url": "https://example.com/feed.xml",
        "active": True,
    }
    base.update(over)
    return base


def _create(client: TestClient, slug: str, **over: object) -> dict:
    resp = client.post(f"{BASE}/instances", json={
        "kind": "source", "slug": slug, "payload": _payload(**over),
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


def _fake_preview(adapter: str, url: str | None, limit: int = 5) -> dict:
    return {
        "adapter": adapter,
        "url_origin": "https://example.com",
        "count": 1,
        "samples": [{
            "title": "sample", "summary": None, "content_chars": 3,
            "content_sha256": "abc123", "published_at": None,
        }],
        "ingested": False,
    }


def _validate(client: TestClient, iid: str, number: int) -> dict:
    resp = client.post(f"{BASE}/instances/{iid}/revisions/{number}/validate")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _test(client: TestClient, iid: str, number: int) -> dict:
    resp = client.post(f"{BASE}/instances/{iid}/revisions/{number}/test", json={"limit": 1})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _activate(client: TestClient, iid: str, number: int, expected: int) -> dict:
    resp = client.post(f"{BASE}/instances/{iid}/revisions/{number}/activate",
                       json={"expected_revision": expected})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------- descriptor contract ----------

def test_definitions_come_from_adapter_registry(client: TestClient) -> None:
    resp = client.get(f"{BASE}/definitions")
    assert resp.status_code == 200
    kinds = {d["kind"]: d for d in resp.json()}
    assert "source" in kinds
    source = kinds["source"]
    assert tuple(source["adapters"]) == ADAPTERS
    assert tuple(source["preview_adapters"]) == PREVIEW_ADAPTERS
    assert {f["name"] for f in source["fields"]} >= {"name", "feed_url", "endpoint_config"}

    one = client.get(f"{BASE}/definitions/source")
    assert one.status_code == 200
    assert one.json()["version"] == source["version"]

    missing = client.get(f"{BASE}/definitions/nope")
    assert missing.status_code == 404


def test_unknown_kind_is_rejected(client: TestClient) -> None:
    resp = client.post(f"{BASE}/instances", json={
        "kind": "nope", "slug": "x", "payload": {},
    })
    assert resp.status_code == 404
    assert client.get(f"{BASE}/instances/{uuid.uuid4()}").status_code == 404


# ---------- revisions + optimistic locking ----------

def test_revision_numbering_and_optimistic_locking(client: TestClient) -> None:
    inst = _create(client, "lock-source")
    iid = inst["id"]
    assert inst["latest_revision"] == 1
    assert inst["revisions"][0]["status"] == "draft"

    stale = client.post(f"{BASE}/instances/{iid}/revisions", json={
        "payload": _payload(feed_url="https://example.com/v2.xml"), "expected_revision": 0,
    })
    assert stale.status_code == 409, stale.text

    ok = client.post(f"{BASE}/instances/{iid}/revisions", json={
        "payload": _payload(feed_url="https://example.com/v2.xml"), "expected_revision": 1,
    })
    assert ok.status_code == 200, ok.text
    assert ok.json()["revision_number"] == 2
    detail = client.get(f"{BASE}/instances/{iid}").json()
    assert [r["revision_number"] for r in detail["revisions"]] == [1, 2]


# ---------- deterministic validation ----------

def test_validation_reports_issues_without_writing(client: TestClient) -> None:
    inst = _create(client, "validation-source", feed_url=None)
    iid = inst["id"]
    body = _validate(client, iid, 1)
    assert body["result"]["ok"] is False
    codes = {i["code"] for i in body["result"]["issues"]}
    assert "no_usable_endpoint" in codes
    assert body["revision"]["status"] == "draft"


def test_validation_rejects_private_url_and_unknown_field(client: TestClient) -> None:
    inst = _create(client, "unsafe-source", feed_url="http://127.0.0.1/feed.xml")
    body = _validate(client, inst["id"], 1)
    assert body["result"]["ok"] is False
    assert any(i["code"] == "unsafe_url" for i in body["result"]["issues"])

    inst2 = _create(client, "extra-field-source", unexpected="x")
    body2 = _validate(client, inst2["id"], 1)
    assert any(i["code"] == "unknown_field" for i in body2["result"]["issues"])


# ---------- lifecycle: validate → test → activate ----------

def test_test_requires_validation_and_never_ingests(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("backend.configuration.service.preview_fetch", _fake_preview)
    before = len(client.get("/api/ingest/documents?limit=500").json())

    inst = _create(client, "lifecycle-source")
    iid = inst["id"]

    early = client.post(f"{BASE}/instances/{iid}/revisions/1/test", json={"limit": 3})
    assert early.status_code == 409

    _validate(client, iid, 1)
    body = _test(client, iid, 1)
    assert body["revision"]["status"] == "tested"
    assert body["result"]["ingested"] is False
    assert body["result"]["count"] == 1
    assert body["result"]["ok"] is True

    after = len(client.get("/api/ingest/documents?limit=500").json())
    assert after == before


def test_activate_requires_tested_and_archives_previous(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("backend.configuration.service.preview_fetch", _fake_preview)
    inst = _create(client, "activate-source")
    iid = inst["id"]

    blocked = client.post(f"{BASE}/instances/{iid}/revisions/1/activate",
                          json={"expected_revision": 1})
    assert blocked.status_code == 409

    _validate(client, iid, 1)
    _test(client, iid, 1)

    stale = client.post(f"{BASE}/instances/{iid}/revisions/1/activate",
                        json={"expected_revision": 0})
    assert stale.status_code == 409

    assert _activate(client, iid, 1, 1)["status"] == "active"

    # revision فعال تغییرناپذیر است
    immutable = client.post(f"{BASE}/instances/{iid}/revisions/1/validate")
    assert immutable.status_code == 409

    client.post(f"{BASE}/instances/{iid}/revisions", json={
        "payload": _payload(feed_url="https://example.com/v2.xml"), "expected_revision": 1,
    })
    _validate(client, iid, 2)
    _test(client, iid, 2)
    _activate(client, iid, 2, 2)

    detail = client.get(f"{BASE}/instances/{iid}").json()
    statuses = {r["revision_number"]: r["status"] for r in detail["revisions"]}
    assert statuses[1] == "archived"
    assert statuses[2] == "active"
    assert detail["active_revision"] == 2

    audit = client.get("/api/audit/records", params={"action": "configuration_activate"})
    assert audit.status_code == 200
    assert any(r.get("target_id") == iid for r in audit.json())


def test_rollback_creates_new_active_revision(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("backend.configuration.service.preview_fetch", _fake_preview)
    inst = _create(client, "rollback-source")
    iid = inst["id"]

    _validate(client, iid, 1)
    _test(client, iid, 1)
    _activate(client, iid, 1, 1)

    client.post(f"{BASE}/instances/{iid}/revisions", json={
        "payload": _payload(feed_url="https://example.com/v2.xml"), "expected_revision": 1,
    })
    _validate(client, iid, 2)
    _test(client, iid, 2)
    _activate(client, iid, 2, 2)

    rolled = client.post(f"{BASE}/instances/{iid}/rollback", json={
        "target_revision": 1, "expected_revision": 2,
    })
    assert rolled.status_code == 200, rolled.text
    body = rolled.json()
    assert body["revision_number"] == 3
    assert body["status"] == "active"
    assert body["payload"]["feed_url"] == "https://example.com/feed.xml"
    assert body["test"]["network_test_skipped"] is True

    detail = client.get(f"{BASE}/instances/{iid}").json()
    statuses = {r["revision_number"]: r["status"] for r in detail["revisions"]}
    assert statuses[1] == "archived"
    assert statuses[2] == "archived"
    assert statuses[3] == "active"
    assert detail["active_revision"] == 3


# ---------- preview safety (no network, no DB) ----------

def test_preview_rejects_private_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preview_mod, "connection_check", lambda url: UrlCheck(False, "private_ip"))
    with pytest.raises(preview_mod.PreviewError):
        preview_mod.preview_fetch("rss", "http://127.0.0.1/feed.xml")


def test_preview_refuses_unsupported_adapter() -> None:
    with pytest.raises(preview_mod.UnsupportedAdapter):
        preview_mod.preview_fetch("csv", "https://example.com/data.csv")


def test_url_policy_blocks_loopback_and_scheme() -> None:
    assert validate_url("http://127.0.0.1/x").ok is False
    assert validate_url("file:///etc/passwd").ok is False
    assert validate_url("https://example.com/x").ok is True


def test_preview_result_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Item:
        title = "t" * 400
        summary = "s" * 600
        content = "body"
        published_at = None

    class _Adapter:
        async def fetch(self, *, url: str | None, limit: int = 20) -> list[object]:
            return [_Item()]

    monkeypatch.setattr(preview_mod, "connection_check", lambda url: UrlCheck(True, ""))
    monkeypatch.setattr("source_bot.adapters.rss.BotRSSAdapter", lambda *a, **k: _Adapter())
    out = preview_mod.preview_fetch("rss", "https://example.com/feed?token=SECRET", limit=5)
    assert out["ingested"] is False
    assert out["url_origin"] == "https://example.com"
    assert "SECRET" not in json.dumps(out)
    assert len(out["samples"][0]["title"]) <= preview_mod.MAX_TITLE_CHARS
    assert len(out["samples"][0]["summary"]) <= preview_mod.MAX_SUMMARY_CHARS
