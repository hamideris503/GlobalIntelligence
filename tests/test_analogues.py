"""Tests for Historical Analogue service & API (Phase 20, اصلاح ممیزی)."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.database.models.memory import MemoryRecord
from backend.database.models.world_state import WorldState
from domains.analogue import similarity as sim
from domains.analogue.engine import AnalogueService
from tests.conftest import TestingSession

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _meta_all(method: str = "test_v1", conf: float = 0.9) -> dict:
    return {
        name: {"value": 0.5, "method": method, "confidence": conf}
        for name in sim.SIGNAL_ORDER
    }


def _seed_state(
    signals: dict, days_ago: int, regime: str = "neutral", meta: dict | None = None
) -> str:
    session = TestingSession()
    try:
        s = WorldState(
            captured_at=BASE - timedelta(days=days_ago),
            granularity="daily",
            macro_regime=regime,
            market_regime="neutral",
            confidence=0.5,
            value_metadata=json.dumps(meta if meta is not None else _meta_all()),
        )
        for k, v in signals.items():
            setattr(s, k, v)
        session.add(s)
        session.commit()
        return str(s.id)
    finally:
        session.close()


def _full(value: float) -> dict:
    return {name: value for name in sim.SIGNAL_ORDER}


# --- pure similarity tests ---
def test_to_vector_none_is_neutral() -> None:
    assert sim.to_vector({}) == [0.5] * 9


def test_euclidean_and_similarity() -> None:
    a = [0.0] * 9
    b = [1.0] * 9
    assert sim.euclidean(a, a) == 0.0
    assert sim.similarity(0.0, "euclidean") == 1.0
    assert sim.euclidean(a, b) == 3.0
    assert abs(sim.similarity(3.0, "euclidean") - 0.25) < 1e-9


def test_cosine_identical_is_one() -> None:
    a = [0.2, 0.8] + [0.5] * 7
    assert abs(sim.cosine_distance(a, a)) < 1e-9
    assert sim.similarity(0.0, "cosine") == 1.0


def test_cosine_detects_level_shift() -> None:
    """یافته‌ی ممیزی: 0.5 در برابر 0.6 نباید شباهت 1 بگیرد."""
    a = [0.5] * 9
    b = [0.6] * 9
    # خام: عملاً هم‌جهت‌اند، اما مرکزدهی اختلاف سطح را آشکار می‌کند
    assert sim.cosine_distance(a, b) == 1.0
    assert sim.similarity(1.0, "cosine") == 0.5


def test_cosine_both_neutral_is_zero() -> None:
    """دو وضعیت کاملاً خنثی جهت ندارند اما یکسان‌اند."""
    assert sim.cosine_distance([0.5] * 9, [0.5] * 9) == 0.0


def test_cosine_neutral_vs_directional() -> None:
    """خنثی در برابر جهت‌دار: فاصله 1.0، بدون NaN و بدون شباهت گمراه‌کننده."""
    a = [0.5] * 9
    b = [0.5] * 8 + [0.9]
    assert sim.cosine_distance(a, b) == 1.0
    assert sim.similarity(1.0, "cosine") == 0.5


def test_normalize_euclidean() -> None:
    assert sim.normalize_euclidean(0.5, 9) == 0.5
    assert abs(sim.normalize_euclidean(0.173205, 3) - 0.3) < 1e-4
    try:
        sim.normalize_euclidean(0.5, 0)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_deltas() -> None:
    d = sim.deltas([0.5] * 9, [0.7] * 9)
    assert set(d) == set(sim.SIGNAL_ORDER)
    assert d["growth_pressure"] == 0.2


# --- service tests ---
def test_find_analogues_ranks_nearest_first() -> None:
    ref = _seed_state(_full(0.5), days_ago=0)  # مرجع: امروز
    near = _seed_state(_full(0.6), days_ago=10)  # نزدیک
    far = _seed_state(_full(0.0), days_ago=20)  # دور
    session = TestingSession()
    try:
        outcome = AnalogueService(session).find_analogues(
            snapshot_id=ref, top_k=5
        )
        assert outcome.reference_id == ref
        assert [h.snapshot_id for h in outcome.hits] == [near, far]
        assert outcome.hits[0].similarity > outcome.hits[1].similarity
        # فقط گذشته لحاظ می‌شود، نه خود مرجع
        assert ref not in [h.snapshot_id for h in outcome.hits]
        assert outcome.hits[0].compared_dims == 9
        assert outcome.hits[0].coverage == 1.0
    finally:
        session.close()


def test_find_analogues_defaults_to_latest() -> None:
    _seed_state(_full(0.1), days_ago=30)
    ref = _seed_state(_full(0.5), days_ago=0)
    session = TestingSession()
    try:
        outcome = AnalogueService(session).find_analogues()
        assert outcome.reference_id == ref
        assert len(outcome.hits) == 1
    finally:
        session.close()


def test_find_analogues_cosine_metric() -> None:
    ref = _seed_state(_full(0.5), days_ago=0)
    _seed_state(_full(0.5), days_ago=5)
    session = TestingSession()
    try:
        outcome = AnalogueService(session).find_analogues(
            snapshot_id=ref, metric="cosine"
        )
        assert outcome.metric == "cosine"
        assert outcome.hits[0].distance == 0.0
        assert outcome.hits[0].similarity == 1.0
    finally:
        session.close()


def test_find_analogues_bad_metric() -> None:
    ref = _seed_state(_full(0.5), days_ago=0)
    session = TestingSession()
    try:
        try:
            AnalogueService(session).find_analogues(snapshot_id=ref, metric="nope")
        except ValueError as exc:
            assert "unknown metric" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected ValueError")
    finally:
        session.close()


def test_find_analogues_missing_reference() -> None:
    session = TestingSession()
    try:
        try:
            AnalogueService(session).find_analogues(
                snapshot_id="00000000-0000-0000-0000-000000000000"
            )
        except LookupError:
            pass
        else:  # pragma: no cover
            raise AssertionError("expected LookupError")
    finally:
        session.close()


def test_no_data_dims_excluded_and_reported() -> None:
    """یافته‌ی ممیزی: no_data خنثی واقعی فرض نمی‌شود؛ پوشش گزارش می‌شود."""
    ref = _seed_state(_full(0.5), days_ago=0)
    meta = _meta_all()
    for name in list(sim.SIGNAL_ORDER)[:3]:
        meta[name] = {"value": 0.5, "method": "no_data", "confidence": 0.1}
    cand = _seed_state(_full(0.5), days_ago=10, meta=meta)
    session = TestingSession()
    try:
        outcome = AnalogueService(session).find_analogues(snapshot_id=ref)
        assert len(outcome.hits) == 1
        hit = outcome.hits[0]
        assert hit.snapshot_id == cand
        assert hit.compared_dims == 6
        assert hit.coverage == round(6 / 9, 3)
        assert set(hit.deltas) == set(sim.SIGNAL_ORDER[3:])
    finally:
        session.close()


def test_low_confidence_dims_excluded() -> None:
    ref = _seed_state(_full(0.5), days_ago=0)
    meta = _meta_all()
    meta["growth_pressure"] = {"value": 0.9, "method": "test_v1", "confidence": 0.2}
    _seed_state(_full(0.5), days_ago=10, meta=meta)
    session = TestingSession()
    try:
        outcome = AnalogueService(session).find_analogues(snapshot_id=ref)
        assert outcome.hits[0].compared_dims == 8
        assert "growth_pressure" not in outcome.hits[0].deltas
    finally:
        session.close()


def test_insufficient_coverage_refused() -> None:
    """مرجع با کمتر از ۳ بُعد معتبر → خطای صریح، نه شباهت ساختگی."""
    meta = _meta_all()
    for name in list(sim.SIGNAL_ORDER)[:7]:
        meta[name] = {"value": 0.5, "method": "no_data", "confidence": 0.1}
    ref = _seed_state(_full(0.5), days_ago=0, meta=meta)
    _seed_state(_full(0.5), days_ago=10)
    session = TestingSession()
    try:
        try:
            AnalogueService(session).find_analogues(snapshot_id=ref)
        except ValueError as exc:
            assert "valid dims" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("expected ValueError")
    finally:
        session.close()


def test_candidate_below_threshold_skipped() -> None:
    ref = _seed_state(_full(0.5), days_ago=0)
    meta = _meta_all()
    for name in list(sim.SIGNAL_ORDER)[:8]:
        meta[name] = {"value": 0.5, "method": "no_data", "confidence": 0.1}
    _seed_state(_full(0.5), days_ago=10, meta=meta)  # فقط ۱ بُعد مشترک
    session = TestingSession()
    try:
        outcome = AnalogueService(session).find_analogues(snapshot_id=ref)
        assert outcome.hits == []
    finally:
        session.close()


def test_aftermath_returns_next_states_and_events() -> None:
    analogue = _seed_state(_full(0.2), days_ago=20)
    nxt = _seed_state(_full(0.9), days_ago=5)
    session = TestingSession()
    try:
        session.add(
            MemoryRecord(
                layer="event",
                ref_type="event",
                ref_id="x",
                title="later shock",
                observed_at=BASE - timedelta(days=10),
                recorded_at=BASE,
            )
        )
        session.commit()
        out = AnalogueService(session).aftermath(analogue_id=analogue)
        assert [s["snapshot_id"] for s in out.next_snapshots] == [nxt]
        assert [e["title"] for e in out.next_events] == ["later shock"]
    finally:
        session.close()


# --- API tests ---
def test_analogues_api(client: TestClient) -> None:
    ref = _seed_state(_full(0.5), days_ago=0)
    _seed_state(_full(0.6), days_ago=10)
    res = client.get(f"/api/analogues?snapshot_id={ref}&top_k=5")
    assert res.status_code == 200
    body = res.json()
    assert body["reference_id"] == ref
    assert len(body["hits"]) == 1
    assert body["hits"][0]["similarity"] > 0.7
    assert body["hits"][0]["compared_dims"] == 9
    assert body["hits"][0]["coverage"] == 1.0
    assert body["valid_dims"] == 9

    after = client.get(f"/api/analogues/{body['hits'][0]['snapshot_id']}/aftermath")
    assert after.status_code == 200
    assert after.json()["analogue_id"] == body["hits"][0]["snapshot_id"]


def test_analogues_api_errors(client: TestClient) -> None:
    assert client.get("/api/analogues?metric=nope").status_code in (404, 422)
    assert (
        client.get("/api/analogues/00000000-0000-0000-0000-000000000000/aftermath").status_code
        == 404
    )


def test_analogues_api_insufficient_coverage_422(client: TestClient) -> None:
    meta = _meta_all()
    for name in list(sim.SIGNAL_ORDER)[:7]:
        meta[name] = {"value": 0.5, "method": "no_data", "confidence": 0.1}
    ref = _seed_state(_full(0.5), days_ago=0, meta=meta)
    res = client.get(f"/api/analogues?snapshot_id={ref}")
    assert res.status_code == 422
