"""WP-06 — Configuration Control Plane: lifecycle، audit، NEEDS_ADAPTER، runtime pin.

پوشش‌ها:
- تعریف‌ها: `source` آماده و creatable؛ گروه‌های بدون adapter صریحاً `needs_adapter`.
- ذخیرهٔ پیکربندی برای kind بدون adapter ممکن نیست (409، بدون ردیف جعلی).
- چرخهٔ کامل از طریق API: draft → validated → tested → active → rollback.
- Draft هیچ اثری روی runtime ندارد؛ بعد از activation، `resolve_source_plan` همان
  payload پین‌شده را برمی‌گرداند (مصرف‌کنندهٔ واقعی: `source_bot.runner`).
- Optimistic locking: `expected_revision` کهنه → 409.
- Audit: هر گذار رکورد `audit_records` دارد.
- Test بدون ingest: هیچ Document/Article جدیدی ساخته نمی‌شود.
- payload با مقدار secret واقعی به‌جای نام متغیر env رد می‌شود.
"""
from __future__ import annotations

import json

from backend.database.models.article import Article
from backend.database.models.audit_record import AuditRecord
from backend.database.models.configuration import ConfigurationInstance
from backend.database.models.document import Document
from backend.database.models.source import Source
from tests.conftest import TestingSession

LIVE_FEED = "https://live.example.com/feed.xml"
PINNED_FEED = "https://pinned.example.com/feed.xml"

VALID_PAYLOAD = {
    "name": "PlaneSrc",
    "type": "rss",
    "collection_method": "rss",
    "feed_url": PINNED_FEED,
    "active": True,
}


def _rows(model) -> int:  # noqa: ANN001 - شمارش خواندنی
    session = TestingSession()
    try:
        return session.query(model).count()
    finally:
        session.close()


def _fake_preview(adapter: str, url: str | None, limit: int = 5) -> dict:  # noqa: ANN001
    """همان قرارداد preview_fetch، بدون شبکه و بدون نوشتن."""
    return {
        "adapter": adapter,
        "url_origin": "https://pinned.example.com",
        "count": 2,
        "samples": [{"title": "sample", "content_chars": 10}],
        "ingested": False,
    }


def _create(client, slug: str = "PlaneSrc") -> dict:  # noqa: ANN001
    resp = client.post(
        "/api/configuration/instances",
        json={"kind": "source", "slug": slug, "payload": VALID_PAYLOAD, "note": "wp06"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _activate_flow(client, monkeypatch, slug: str = "PlaneSrc") -> dict:  # noqa: ANN001
    monkeypatch.setattr("backend.configuration.service.preview_fetch", _fake_preview)
    inst = _create(client, slug)
    iid = inst["id"]
    assert inst["revisions"][0]["status"] == "draft"

    val = client.post(f"/api/configuration/instances/{iid}/revisions/1/validate")
    assert val.status_code == 200, val.text
    assert val.json()["result"]["ok"] is True
    assert val.json()["revision"]["status"] == "validated"

    test = client.post(
        f"/api/configuration/instances/{iid}/revisions/1/test", json={"limit": 2}
    )
    assert test.status_code == 200, test.text
    assert test.json()["revision"]["status"] == "tested"

    act = client.post(
        f"/api/configuration/instances/{iid}/revisions/1/activate",
        json={"expected_revision": 1},
    )
    assert act.status_code == 200, act.text
    assert act.json()["status"] == "active"
    return client.get(f"/api/configuration/instances/{iid}").json()


def test_definitions_expose_needs_adapter_groups(client) -> None:  # noqa: ANN001
    defs = client.get("/api/configuration/definitions").json()
    by_kind = {d["kind"]: d for d in defs}
    assert by_kind["source"]["adapter_state"] == "ready"
    assert by_kind["source"]["creatable"] is True
    assert by_kind["source"]["adapters"], "source باید adapter واقعی داشته باشد"
    for kind in ("email", "telegram", "scheduling", "ui_preferences", "access_security"):
        assert by_kind[kind]["adapter_state"] == "needs_adapter", kind
        assert by_kind[kind]["creatable"] is False, kind
        assert by_kind[kind]["note"], kind


def test_needs_adapter_kind_cannot_be_stored(client) -> None:  # noqa: ANN001
    before = _rows(ConfigurationInstance)
    resp = client.post(
        "/api/configuration/instances",
        json={"kind": "scheduling", "slug": "cron", "payload": {"cron": "* * * * *"}},
    )
    assert resp.status_code == 409, resp.text
    assert "NEEDS_ADAPTER" in resp.text
    assert _rows(ConfigurationInstance) == before, "هیچ instance جعلی نباید ساخته شود"


def test_unknown_kind_is_404(client) -> None:  # noqa: ANN001
    resp = client.post(
        "/api/configuration/instances",
        json={"kind": "nope", "slug": "x", "payload": {}},
    )
    assert resp.status_code == 404


def test_full_lifecycle_pins_runtime_and_audits(client, monkeypatch) -> None:  # noqa: ANN001
    session = TestingSession()
    try:
        session.add(Source(name="PlaneSrc", domain="plane.local", type="rss",
                           collection_method="rss", feed_url=LIVE_FEED, active=True))
        session.commit()
    finally:
        session.close()

    detail = _activate_flow(client, monkeypatch)
    assert detail["active_revision"] == 1
    statuses = [r["status"] for r in detail["revisions"]]
    assert statuses == ["active"]

    # مصرف‌کنندهٔ runtime: پین‌شده بر ردیف زنده اولویت دارد.
    from backend.configuration.runtime import resolve_source_plan
    session = TestingSession()
    try:
        source = session.query(Source).filter(Source.name == "PlaneSrc").one()
        plan, revision = resolve_source_plan(session, source)
        assert revision == 1
        assert plan.url == PINNED_FEED
    finally:
        session.close()

    actions = {a.action for a in _audit_rows()}
    assert {"configuration_create", "configuration_validate",
            "configuration_test", "configuration_activate"} <= actions


def _audit_rows() -> list[AuditRecord]:
    session = TestingSession()
    try:
        return session.query(AuditRecord).all()
    finally:
        session.close()


def test_draft_does_not_change_runtime(client) -> None:  # noqa: ANN001
    session = TestingSession()
    try:
        session.add(Source(name="DraftOnly", domain="plane.local", type="rss",
                           collection_method="rss", feed_url=LIVE_FEED, active=True))
        session.commit()
    finally:
        session.close()

    inst = _create(client, "DraftOnly")
    assert client.post(
        f"/api/configuration/instances/{inst['id']}/revisions/1/validate"
    ).status_code == 200

    from backend.configuration.runtime import resolve_source_plan
    session = TestingSession()
    try:
        source = session.query(Source).filter(Source.name == "DraftOnly").one()
        plan, revision = resolve_source_plan(session, source)
        assert revision is None, "Draft نباید در runtime پین شود"
        assert plan.url == LIVE_FEED
    finally:
        session.close()


def test_optimistic_locking_rejects_stale_revision(client, monkeypatch) -> None:  # noqa: ANN001
    inst = _create(client, "LockSrc")
    iid = inst["id"]
    stale = client.post(
        f"/api/configuration/instances/{iid}/revisions",
        json={"payload": VALID_PAYLOAD, "expected_revision": 99},
    )
    assert stale.status_code == 409

    ok = client.post(
        f"/api/configuration/instances/{iid}/revisions",
        json={"payload": VALID_PAYLOAD, "expected_revision": 1},
    )
    assert ok.status_code == 200
    assert ok.json()["revision_number"] == 2

    # فعال‌سازی با نسخهٔ کهنه هم رد می‌شود.
    monkeypatch.setattr("backend.configuration.service.preview_fetch", _fake_preview)
    client.post(f"/api/configuration/instances/{iid}/revisions/2/validate")
    client.post(f"/api/configuration/instances/{iid}/revisions/2/test", json={"limit": 1})
    resp = client.post(
        f"/api/configuration/instances/{iid}/revisions/2/activate",
        json={"expected_revision": 1},
    )
    assert resp.status_code == 409


def test_activate_requires_tested_revision(client) -> None:  # noqa: ANN001
    inst = _create(client, "GuardSrc")
    iid = inst["id"]
    client.post(f"/api/configuration/instances/{iid}/revisions/1/validate")
    resp = client.post(
        f"/api/configuration/instances/{iid}/revisions/1/activate",
        json={"expected_revision": 1},
    )
    assert resp.status_code == 409
    assert "tested" in resp.text


def test_test_step_does_not_ingest(client, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setattr("backend.configuration.service.preview_fetch", _fake_preview)
    inst = _create(client, "NoIngest")
    iid = inst["id"]
    docs_before, arts_before = _rows(Document), _rows(Article)
    client.post(f"/api/configuration/instances/{iid}/revisions/1/validate")
    resp = client.post(f"/api/configuration/instances/{iid}/revisions/1/test",
                       json={"limit": 2})
    assert resp.status_code == 200, resp.text
    assert _rows(Document) == docs_before
    assert _rows(Article) == arts_before


def test_rollback_creates_new_active_revision(client, monkeypatch) -> None:  # noqa: ANN001
    detail = _activate_flow(client, monkeypatch, slug="RollSrc")
    iid = detail["id"]

    changed = dict(VALID_PAYLOAD, feed_url="https://changed.example.com/feed.xml")
    new = client.post(
        f"/api/configuration/instances/{iid}/revisions",
        json={"payload": changed, "expected_revision": 1},
    )
    assert new.status_code == 200
    client.post(f"/api/configuration/instances/{iid}/revisions/2/validate")
    client.post(f"/api/configuration/instances/{iid}/revisions/2/test", json={"limit": 1})
    client.post(f"/api/configuration/instances/{iid}/revisions/2/activate",
                json={"expected_revision": 2})

    rb = client.post(
        f"/api/configuration/instances/{iid}/rollback",
        json={"target_revision": 1, "expected_revision": 2},
    )
    assert rb.status_code == 200, rb.text
    body = rb.json()
    assert body["revision_number"] == 3
    assert body["status"] == "active"
    assert body["payload"]["feed_url"] == PINNED_FEED

    after = client.get(f"/api/configuration/instances/{iid}").json()
    assert after["active_revision"] == 3
    statuses = {r["revision_number"]: r["status"] for r in after["revisions"]}
    assert statuses == {1: "archived", 2: "archived", 3: "active"}


def test_secret_value_in_payload_is_rejected(client) -> None:  # noqa: ANN001
    payload = dict(VALID_PAYLOAD, endpoint_config={"api_key_env": "sk-live-123456"})
    resp = client.post(
        "/api/configuration/instances",
        json={"kind": "source", "slug": "LeakSrc", "payload": payload},
    )
    assert resp.status_code == 200  # ساخت Draft مجاز است…
    iid = resp.json()["id"]
    val = client.post(f"/api/configuration/instances/{iid}/revisions/1/validate")
    assert val.status_code == 200
    assert val.json()["result"]["ok"] is False
    codes = {i["code"] for i in val.json()["result"]["issues"]}
    assert "secret_value" in codes, codes
    # مقدار secret در پاسخ بازخوانی نمی‌شود.
    assert "sk-live-123456" not in json.dumps(val.json())
