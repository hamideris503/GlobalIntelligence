"""صفحه‌بندی مشترک (مرحله ۲): حدود، allowlist مرتب‌سازی، has_more، سازگاری."""
from __future__ import annotations

import pytest

from backend.api.errors import ApiError
from backend.api.pagination import (
    MAX_PAGE_SIZE,
    PageParams,
    page_params,
    page_response,
)


def test_defaults_are_page_one_and_fifty() -> None:
    params = page_params()
    assert (params.page, params.page_size, params.offset) == (1, 50, 0)


def test_legacy_limit_and_offset_still_work() -> None:
    params = page_params(limit=10, offset=20)
    assert params.page_size == 10
    assert params.offset == 20
    assert params.page == 3


def test_bounds_are_enforced() -> None:
    with pytest.raises(ApiError) as too_big:
        page_params(page_size=MAX_PAGE_SIZE + 1)
    assert too_big.value.status_code == 422
    assert too_big.value.code == "VALIDATION_ERROR"
    with pytest.raises(ApiError):
        page_params(page=0)
    with pytest.raises(ApiError):
        page_params(page_size=0)
    with pytest.raises(ApiError):
        page_params(offset=-1)


def test_custom_max_size_is_honoured() -> None:
    assert page_params(page_size=100, max_size=100).page_size == 100
    with pytest.raises(ApiError):
        page_params(page_size=101, max_size=100)


def test_sort_allowlist_accepts_known_fields_only() -> None:
    params = page_params(sort="-name", sortable=("name", "country"))
    assert params.sort == "-name"
    with pytest.raises(ApiError) as bad:
        page_params(sort="drop table", sortable=("name",))
    assert bad.value.details["fields"]["sort"]
    assert bad.value.details["allowed"] == ["name"]


def test_sort_is_rejected_when_not_supported() -> None:
    with pytest.raises(ApiError):
        page_params(sort="name")


def test_has_more_follows_total() -> None:
    params = PageParams(page=1, page_size=2, offset=0)
    assert page_response([1, 2], 3, params)["has_more"] is True
    assert page_response([1, 2], 2, params)["has_more"] is False
    assert page_response([], 0, params)["total"] == 0


def test_sources_page_envelope_and_sorting(client) -> None:
    for name in ("Gamma", "Alpha", "Beta"):
        client.post("/api/sources", json={"name": name, "type": "rss"})

    first = client.get("/api/sources", params={"page": 1, "page_size": 2, "sort": "name"})
    assert first.status_code == 200
    body = first.json()
    assert set(body) == {"items", "total", "page", "page_size", "has_more"}
    assert body["total"] == 3 and len(body["items"]) == 2
    assert body["has_more"] is True
    assert [s["name"] for s in body["items"]] == ["Alpha", "Beta"]

    second = client.get("/api/sources", params={"page": 2, "page_size": 2, "sort": "name"})
    assert second.json()["has_more"] is False
    assert [s["name"] for s in second.json()["items"]] == ["Gamma"]


def test_sources_legacy_list_is_unchanged(client) -> None:
    client.post("/api/sources", json={"name": "Only", "type": "rss"})
    res = client.get("/api/sources", params={"limit": 100})
    assert res.status_code == 200
    assert isinstance(res.json(), list)
    assert res.json()[0]["name"] == "Only"


def test_sources_invalid_sort_is_422(client) -> None:
    res = client.get("/api/sources", params={"page": 1, "sort": "nope"})
    assert res.status_code == 422
    body = res.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "sort" in body["error"]["details"]["fields"]


def test_events_page_envelope(client) -> None:
    res = client.get("/api/events", params={"page": 1, "page_size": 5})
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"items", "total", "page", "page_size", "has_more"}
    assert body["total"] == 0 and body["items"] == []
    legacy = client.get("/api/events", params={"limit": 5})
    assert isinstance(legacy.json(), list)


def test_screening_queue_reports_total(client) -> None:
    res = client.get("/api/screening/queue")
    assert res.status_code == 200
    body = res.json()
    assert {"items", "total", "page", "page_size", "has_more"} <= set(body)
    assert body["total"] == 0
    assert client.get(
        "/api/screening/queue", params={"page_size": 101}
    ).status_code == 422
