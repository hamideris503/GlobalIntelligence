"""Tests for Audit log & Replay (Phase 38)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.database.models.audit_record import AuditRecord
from backend.database.models.market import MacroObservation
from domains.audit.replay import SUPPORTED_ENGINES, fingerprint, replay
from domains.audit.service import log_action
from tests.conftest import TestingSession


def _seed_macro(indicator: str, country: str, rows: list[tuple[str, float]]) -> None:
    session = TestingSession()
    try:
        for period, value in rows:
            session.add(
                MacroObservation(
                    indicator=indicator,
                    country=country,
                    period=period,
                    value=value,
                    source_name="test",
                )
            )
        session.commit()
    finally:
        session.close()


# --- service tests ---
def test_log_action_stores_record() -> None:
    session = TestingSession()
    try:
        rec = log_action(
            session, action="macro.analyze", actor="cli", result={"stored": 2}
        )
        assert rec.id is not None
        assert session.query(AuditRecord).count() == 1
    finally:
        session.close()


def test_log_is_append_only() -> None:
    session = TestingSession()
    try:
        log_action(session, action="a")
        log_action(session, action="b")
        assert session.query(AuditRecord).count() == 2
    finally:
        session.close()


# --- replay tests ---
def test_supported_engines() -> None:
    assert set(SUPPORTED_ENGINES) == {
        "macro", "risk", "geopolitics", "society", "performance",
    }


def test_replay_macro_matches() -> None:
    _seed_macro("inflation", "USA", [("2023", 4.12), ("2024", 2.95)])
    session = TestingSession()
    try:
        from domains.macro.analysis import MacroEngine

        MacroEngine(session).analyze_all()
        outcome = replay(session, "macro")
        assert outcome.match is True
        assert outcome.digest_before == outcome.digest_after
        assert outcome.rows == 1
        assert outcome.errors == []
    finally:
        session.close()


def test_replay_detects_drift() -> None:
    """دست‌کاری ردیف ذخیره‌شده → mismatch (نه match جعلی)."""
    _seed_macro("inflation", "USA", [("2023", 4.12), ("2024", 2.95)])
    session = TestingSession()
    try:
        from backend.database.models.macro_assessment import MacroAssessment
        from domains.macro.analysis import MacroEngine

        MacroEngine(session).analyze_all()
        row = session.query(MacroAssessment).one()
        row.momentum_label = "tampered"
        session.commit()
        # اجرای دوباره مقدار درست را برمی‌گرداند → digest عوض می‌شود
        outcome = replay(session, "macro")
        assert outcome.match is False
        assert outcome.digest_before != outcome.digest_after
    finally:
        session.close()


def test_replay_unsupported_engine() -> None:
    session = TestingSession()
    try:
        outcome = replay(session, "nope")
        assert outcome.match is False
        assert outcome.errors
    finally:
        session.close()


def test_fingerprint_stable() -> None:
    _seed_macro("gdp", "USA", [("2023", 100.0), ("2024", 103.0)])
    session = TestingSession()
    try:
        from domains.macro.analysis import MacroEngine

        MacroEngine(session).analyze_all()
        d1, n1 = fingerprint(session, "macro")
        d2, n2 = fingerprint(session, "macro")
        assert d1 == d2 and n1 == n2 == 1
    finally:
        session.close()


# --- API tests ---
def test_audit_api(client: TestClient) -> None:
    res = client.post(
        "/api/audit/log",
        json={"action": "test.run", "actor": "test", "result": {"ok": True}},
    )
    assert res.status_code == 200
    assert res.json()["action"] == "test.run"

    bad = client.post("/api/audit/log", json={"action": "  "})
    assert bad.status_code == 422

    lst = client.get("/api/audit/records?action=test.run")
    assert lst.status_code == 200
    assert len(lst.json()) == 1

    engines = client.get("/api/audit/engines")
    assert engines.status_code == 200
    assert "macro" in engines.json()["engines"]

    _seed_macro("inflation", "USA", [("2023", 4.12), ("2024", 2.95)])
    from domains.macro.analysis import MacroEngine

    session = TestingSession()
    try:
        MacroEngine(session).analyze_all()
    finally:
        session.close()
    rep = client.post("/api/audit/replay?engine=macro")
    assert rep.status_code == 200
    assert rep.json()["match"] is True

    bad_engine = client.post("/api/audit/replay?engine=nope")
    assert bad_engine.status_code == 422
