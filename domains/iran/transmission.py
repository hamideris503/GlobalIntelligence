"""Transmission Engine — اثر شوک‌های جهانی بر ایران (Phase 34).

ورودی هر کانال (v1):
- energy: میانگین نرمال‌شده‌ی WTI/Brent در باند ۵۰–۱۵۰.
- rates: بازده US10Y تقسیم بر ۱۰.
- geopolitical: بیشینه‌ی (ریسک جهان، تنش بازیگر Iran در آخرین دوره).
- market: افت SPX از سقف ۲۵۲ روزه (همان تعریف Phase 18).

- upsert ماهانه در `transmission_assessments` (idempotent).
- بدون AI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.geopolitical_assessment import GeopoliticalAssessment
from backend.database.models.market import MarketObservation
from backend.database.models.transmission_assessment import TransmissionAssessment
from backend.database.models.world_state import WorldState
from domains.iran.transmission_analytics import transmit
from domains.worldstate.builder import WorldStateBuilder

logger = get_logger(__name__)


@dataclass
class TransmissionOutcome:
    channels_analyzed: int = 0
    stored: int = 0
    duplicates: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "channels_analyzed": self.channels_analyzed,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
        }


def _latest_value(db: Session, symbol: str) -> float | None:
    stmt = (
        select(MarketObservation.value)
        .where(
            MarketObservation.symbol == symbol,
            MarketObservation.value.is_not(None),
        )
        .order_by(MarketObservation.observed_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def _signal_value(snapshot: WorldState, name: str) -> float | None:
    """مقدار سیگنال معتبر (غیر-no_data)؛ وگرنه None."""
    try:
        meta = json.loads(snapshot.value_metadata or "{}")
    except Exception:  # noqa: BLE001
        return None
    entry = meta.get(name)
    if not isinstance(entry, dict) or entry.get("method") == "no_data":
        return None
    try:
        return float(entry.get("value"))
    except (TypeError, ValueError):
        return None


class TransmissionEngine:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._ws = WorldStateBuilder(db)

    def analyze_all(self, *, period: str | None = None) -> TransmissionOutcome:
        outcome = TransmissionOutcome()
        period = period or datetime.now(UTC).strftime("%Y-%m")

        snapshot = self.db.execute(
            select(WorldState).order_by(WorldState.captured_at.desc()).limit(1)
        ).scalars().first()

        inputs: dict[str, tuple[float | None, str]] = {}
        wti = _latest_value(self.db, "WTI")
        brent = _latest_value(self.db, "BRENT")
        oil = [p for p in (wti, brent) if p is not None]
        inputs["energy"] = (
            (sum((p - 50.0) / 100.0 for p in oil) / len(oil), "wti_brent_band_50_150")
            if oil
            else (None, "wti_brent_band_50_150")
        )
        tnx = _latest_value(self.db, "US10Y")
        inputs["rates"] = (
            (tnx / 10.0, "us10y_over_10") if tnx is not None else (None, "us10y_over_10")
        )

        geo_candidates: list[float] = []
        geo_driver = "worldstate:geopolitical"
        if snapshot is not None:
            g = _signal_value(snapshot, "geopolitical_risk")
            if g is not None:
                geo_candidates.append(g)
        iran_tension = self.db.execute(
            select(GeopoliticalAssessment.tension)
            .where(
                GeopoliticalAssessment.actor == "Iran",
                GeopoliticalAssessment.tension.is_not(None),
            )
            .order_by(GeopoliticalAssessment.period.desc())
            .limit(1)
        ).scalars().first()
        if iran_tension is not None:
            geo_candidates.append(float(iran_tension))
            geo_driver = "max(worldstate, iran_tension)"
        inputs["geopolitical"] = (
            (max(geo_candidates), geo_driver) if geo_candidates else (None, geo_driver)
        )

        drawdown = self._ws._spx_drawdown()
        inputs["market"] = (
            (drawdown, "spx_drawdown_252d") if drawdown is not None else (None, "spx_drawdown_252d")
        )

        for channel in ("energy", "rates", "geopolitical", "market"):
            try:
                value, driver = inputs[channel]
                impact = transmit(channel, value, driver)
                if impact is None:
                    outcome.skipped += 1
                    continue
                outcome.channels_analyzed += 1
                existing = self.db.execute(
                    select(TransmissionAssessment).where(
                        TransmissionAssessment.channel == channel,
                        TransmissionAssessment.period == period,
                    )
                ).scalar_one_or_none()
                payload = {
                    "input_value": impact.input_value,
                    "exposure": impact.exposure,
                    "impact": impact.impact,
                    "drivers": json.dumps(impact.drivers, ensure_ascii=False),
                    "method": impact.method,
                    "confidence": impact.confidence,
                    "observed_at": datetime.now(UTC),
                }
                if existing is not None:
                    for k, v in payload.items():
                        setattr(existing, k, v)
                    outcome.duplicates += 1
                else:
                    self.db.add(
                        TransmissionAssessment(
                            channel=channel, period=period, **payload
                        )
                    )
                    self.db.flush()
                    outcome.stored += 1
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("transmission failed | %s err=%s", channel, exc)
        self.db.commit()
        logger.info("transmission done | %s", outcome.as_dict())
        return outcome
