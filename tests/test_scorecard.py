"""Tests for debate scorecard (Step 4) — honest evaluation incl. sample rule."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from backend.database.models.forecast import Forecast, ForecastOutcome
from backend.database.models.market import MarketObservation
from domains.debate.scorecard import MIN_SAMPLES, ScorecardBuilder
from tests.conftest import TestingSession


def _seed_resolved(session, model: str, probs: list[float], actuals: list[bool],
                   symbol: str, tag: str) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    session.add(MarketObservation(
        symbol=symbol, asset_class="energy", value=90.0,
        unit="usd_per_bbl", currency="USD", source_name=f"test-{tag}",
        observed_at=now - timedelta(days=60)))
    session.add(MarketObservation(
        symbol=symbol, asset_class="energy", value=95.0,
        unit="usd_per_bbl", currency="USD", source_name=f"test-{tag}",
        observed_at=now + timedelta(days=1)))
    for p, y in zip(probs, actuals, strict=True):
        fc = Forecast(
            valid_from=now - timedelta(days=60), target_date=now,
            horizon="short", target=f"market:{symbol}", probability=p,
            expected_value=None, confidence=0.6, model=model, status="resolved",
            evidence=json.dumps({"reference_price": 90.0}),
        )
        session.add(fc)
        session.flush()
        session.add(ForecastOutcome(
            forecast_id=fc.id, actual_value=95.0,
            actual_bool="true" if y else "false", resolved_at=now,
        ))
    session.commit()


def test_scorecard_insufficient_sample() -> None:
    session = TestingSession()
    try:
        _seed_resolved(session, "debate_consensus", [0.7] * 5, [True] * 5,
                       symbol="IS1", tag="s1")
        card = ScorecardBuilder(session).build(target="market:IS1")
        assert card.sufficient is False
        assert card.verdict == "insufficient_sample"
        assert "نتیجه‌گیری ممنوع" in card.message
        assert card.n_resolved == 5
        assert any(c.model == "debate_consensus" for c in card.cards)
    finally:
        session.close()


def test_scorecard_declares_winner_when_sufficient() -> None:
    session = TestingSession()
    try:
        n = MIN_SAMPLES
        _seed_resolved(session, "debate_consensus", [0.9] * n, [True] * n,
                       symbol="IS2", tag="s2")
        _seed_resolved(session, "debate:bull:x", [0.6] * n, [True] * n,
                       symbol="IS2", tag="s3")
        card = ScorecardBuilder(session).build(target="market:IS2")
        assert card.sufficient is True
        assert card.verdict == "debate_wins"
        cons = next(c for c in card.cards if c.model == "debate_consensus")
        assert cons.mean_brier is not None and cons.mean_brier < 0.02
        assert cons.hit_rate == 1.0
        assert cons.calibration  # کالیبراسیون محاسبه شده
    finally:
        session.close()


def test_scorecard_baseline_hit_rate() -> None:
    session = TestingSession()
    try:
        now = datetime.now(UTC).replace(microsecond=0)
        session.add(MarketObservation(
            symbol="IS3", asset_class="energy", value=90.0,
            unit="usd_per_bbl", currency="USD", source_name="test-s4",
            observed_at=now - timedelta(days=60)))
        session.add(MarketObservation(
            symbol="IS3", asset_class="energy", value=95.0,
            unit="usd_per_bbl", currency="USD", source_name="test-s4",
            observed_at=now + timedelta(days=1)))
        fc = Forecast(
            valid_from=now - timedelta(days=59), target_date=now,
            horizon="short", target="market:IS3", probability=None,
            expected_value=92.0, confidence=0.5, model="baseline_naive",
            status="resolved", evidence=json.dumps({}),
        )
        session.add(fc)
        session.flush()
        session.add(ForecastOutcome(
            forecast_id=fc.id, actual_value=95.0, actual_bool="true",
            resolved_at=now,
        ))
        session.commit()
        card = ScorecardBuilder(session).build(target="market:IS3")
        base = next(c for c in card.cards if c.model == "baseline_naive")
        assert base.hit_rate == 1.0  # 92 > 90 و actual true
        assert base.mean_brier is None  # baseline احتمال ندارد
        assert card.verdict == "insufficient_sample"
    finally:
        session.close()


def test_scorecard_api(client: TestClient) -> None:
    res = client.get("/api/debate/scorecard")
    assert res.status_code == 200
    body = res.json()
    assert body["verdict"] in ("insufficient_sample", "debate_wins", "no_winner")
    assert "cards" in body
