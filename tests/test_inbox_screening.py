"""مرحلهٔ ۵: صندوق اطلاعات و تصمیم انسانی."""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from backend.auth.deps import CurrentUser, require_user
from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.human_review import HumanReview
from backend.database.models.source import Source
from backend.main import app
from tests.conftest import TestingSession


def _seed_article(*, title="t", priority="P1", status="done", cluster=None,
                  screening=None, event_id=None, source_name="src"):
    s = TestingSession()
    src = s.query(Source).first()
    if src is None:
        src = Source(name="s", type="rss", active=True)
        s.add(src)
        s.flush()
    doc = Document(source_id=src.id, url=f"https://example.com/{uuid.uuid4().hex}", title=title,
                   ingestion_priority=priority)
    s.add(doc)
    s.flush()
    meta = None
    if screening is not None:
        meta = json.dumps({"local_screening": screening}, ensure_ascii=False)
    art = Article(document_id=doc.id, title=title, source_name=source_name,
                  classification_status=status, duplicate_cluster=cluster,
                  classification_meta=meta, event_id=event_id,
                  retrieved_at=datetime.now(UTC))
    s.add(art)
    s.commit()
    aid = art.id
    s.close()
    return aid


class _Role:
    def __init__(self, role):
        self.role = role

    def __enter__(self):
        app.dependency_overrides[require_user] = lambda: CurrentUser(
            username=self.role, role=self.role, via="session"
        )
        return self

    def __exit__(self, *a):
        app.dependency_overrides.pop(require_user, None)


def test_inbox_lists_real_items(client: TestClient) -> None:
    _seed_article(title="hello world", priority="P0")
    body = client.get("/api/inbox").json()
    assert "items" in body and "total" in body
    assert body["total"] >= 1
    item = next(i for i in body["items"] if i["title"] == "hello world")
    assert item["priority"] == "P0"
    assert item["analysis_status"] == "done"


def test_inbox_evidence_status_derived_not_stored(client: TestClient) -> None:
    aid = _seed_article(title="no-event", status="done", event_id=None)
    body = client.get("/api/inbox").json()
    item = next(i for i in body["items"] if i["article_id"] == str(aid))
    assert item["evidence_status"] == "thin"


def test_inbox_filters_and_sort(client: TestClient) -> None:
    _seed_article(title="zzz", priority="P4")
    _seed_article(title="aaa", priority="P0")
    body = client.get("/api/inbox?sort=title&page=1&page_size=50").json()
    titles = [i["title"] for i in body["items"]]
    assert titles.index("aaa") < titles.index("zzz")


def test_inbox_invalid_sort_422(client: TestClient) -> None:
    res = client.get("/api/inbox?sort=nope")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_inbox_invalid_dedup_state_422(client: TestClient) -> None:
    res = client.get("/api/inbox?dedup_state=weird")
    assert res.status_code == 422
    assert "dedup_state" in res.json()["error"]["details"]["fields"]


def test_inbox_pagination_envelope(client: TestClient) -> None:
    for i in range(3):
        _seed_article(title=f"p{i}")
    body = client.get("/api/inbox?page=1&page_size=2").json()
    assert set(body) >= {"items", "total", "page", "page_size", "has_more"}
    assert len(body["items"]) == 2


def test_inbox_summary_definitions(client: TestClient) -> None:
    _seed_article(title="dup", cluster="c1")
    body = client.get("/api/inbox/summary").json()
    assert "definitions" in body
    assert body["duplicate_candidates"] >= 1


def test_inbox_empty_state(client: TestClient) -> None:
    body = client.get("/api/inbox").json()
    assert body["items"] == []
    assert body["total"] == 0


# --- decisions ---------------------------------------------------------------

def test_decision_requires_analyst(client: TestClient) -> None:
    aid = _seed_article(title="dec")
    with _Role("viewer"):
        res = client.post(f"/api/screening/review/{aid}/decision", json={"decision": "approve"})
    assert res.status_code == 403


def test_decision_recorded_and_machine_output_untouched(client: TestClient) -> None:
    screening = {"decision": True, "model": "kev", "confidence": 0.7}
    aid = _seed_article(title="dec2", screening=screening)
    before = TestingSession().get(Article, aid).classification_meta

    with _Role("analyst"):
        res = client.post(f"/api/screening/review/{aid}/decision",
                          json={"decision": "reject", "note": "not relevant"})
    assert res.status_code == 200
    body = res.json()
    assert body["decision"]["action"] == "reject"
    assert body["decision"]["actor"] == "analyst"
    assert len(body["history"]) == 1

    # machine output untouched
    after = TestingSession().get(Article, aid).classification_meta
    assert after == before
    parsed = json.loads(after)
    assert parsed["local_screening"]["decision"] is True

    # persisted in human_reviews, not in classification_meta
    rows = TestingSession().query(HumanReview).all()
    assert any(r.entity_id == aid and r.action == "reject" for r in rows)


def test_decision_request_evidence(client: TestClient) -> None:
    aid = _seed_article(title="dec3")
    with _Role("analyst"):
        res = client.post(f"/api/screening/review/{aid}/decision",
                          json={"decision": "request_evidence"})
    assert res.status_code == 200
    assert res.json()["decision"]["action"] == "request_evidence"


def test_decision_invalid_action_422(client: TestClient) -> None:
    aid = _seed_article(title="dec4")
    with _Role("analyst"):
        res = client.post(f"/api/screening/review/{aid}/decision", json={"decision": "nope"})
    assert res.status_code == 422


def test_decision_unknown_article_404(client: TestClient) -> None:
    with _Role("analyst"):
        res = client.post(f"/api/screening/review/{uuid.uuid4()}/decision",
                          json={"decision": "approve"})
    assert res.status_code == 404


def test_screening_summary(client: TestClient) -> None:
    _seed_article(title="s1", screening={"decision": True})
    _seed_article(title="s2", screening={"decision": False})
    body = client.get("/api/screening/summary").json()
    assert body["relevant"] >= 1
    assert body["not_relevant"] >= 1
    assert "definitions" in body


@pytest.mark.parametrize("role,expected", [("viewer", 200), ("analyst", 200)])
def test_inbox_viewer_can_read(client: TestClient, role: str, expected: int) -> None:
    with _Role(role):
        assert client.get("/api/inbox").status_code == expected
