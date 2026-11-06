"""Replay period regression — replay must not invent a new period.

نقصی که این تست از آن محافظت می‌کند: `rerun()` بدون `period` اجرا می‌شد و موتورهای
دوره‌محور پیش‌فرض «ماه جاری» را می‌گرفتند؛ پس replay دادهٔ ماه قبل، ردیف‌های ماه جدید
می‌ساخت و drift کاذب گزارش می‌کرد.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from backend.database.models.risk_assessment import RiskAssessment
from backend.database.models.world_state import WorldState
from domains.audit.replay import latest_period, replay
from domains.risk.analysis import RiskEngine
from tests.conftest import TestingSession

PERIOD = "2025-01"


def _seed_snapshot(session) -> None:  # noqa: ANN001
    session.add(
        WorldState(
            captured_at=datetime.now(UTC),
            granularity="daily",
            macro_regime="expansion",
            market_regime="neutral",
            inflation_pressure=0.3,
            growth_pressure=0.6,
            confidence=0.5,
            value_metadata=json.dumps(
                {
                    "inflation_pressure": {
                        "value": 0.3, "method": "cpi_over_10", "confidence": 0.7,
                    },
                    "growth_pressure": {
                        "value": 0.6, "method": "gdp_yoy_linear", "confidence": 0.7,
                    },
                }
            ),
        )
    )
    session.commit()


def test_replay_reruns_the_stored_period_not_the_current_month() -> None:
    session = TestingSession()
    try:
        _seed_snapshot(session)
        RiskEngine(session).analyze_all(period=PERIOD)
        assert latest_period(session, "risk") == PERIOD

        before = session.query(RiskAssessment).count()
        outcome = replay(session, "risk")

        assert outcome.errors == []
        assert outcome.match is True
        assert outcome.rows == before  # هیچ دورهٔ جدیدی ساخته نشد
        current = datetime.now(UTC).strftime("%Y-%m")
        assert session.query(RiskAssessment).filter_by(period=current).count() == 0
    finally:
        session.close()


def test_replay_without_data_falls_back_to_now_safely() -> None:
    session = TestingSession()
    try:
        assert latest_period(session, "risk") is None
        outcome = replay(session, "risk")
        # بدون WorldState موتور صادقانه skip می‌کند و ردیفی نمی‌سازد
        assert outcome.errors == []
        assert session.query(RiskAssessment).count() == 0
    finally:
        session.close()
