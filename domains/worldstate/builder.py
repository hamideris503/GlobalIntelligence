"""WorldState Builder — ساخت snapshot وضعیت جهان (Phase 18).

مسیر: macro_observations + market_observations + events/claims/articles
      → signals (قطعی) → یک ردیف `WorldState` با value_metadata کامل.

- هر build یک snapshot جدید می‌سازد (State Memory؛ idempotent نیست by design،
  چون تاریخچه‌ی وضعیت‌ها ارزشمند است).
- هر مقدار دارای value/timestamp/source/method/confidence (بند 33 ARCHITECTURE).
- بدون AI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.claim import Claim
from backend.database.models.event import Event
from backend.database.models.market import MacroObservation, MarketObservation
from backend.database.models.world_state import WorldState
from domains.worldstate import signals as sig

logger = get_logger(__name__)

SIGNAL_NAMES = [
    "growth_pressure",
    "inflation_pressure",
    "liquidity",
    "financial_stress",
    "geopolitical_risk",
    "energy_risk",
    "trade_risk",
    "political_risk",
    "social_pressure",
]

DISPUTED_STATUSES = frozenset({"contradicted", "disputed"})

# پنجره‌ی افت بازار: سقف ۲۵۲ جلسه‌ی اخیر (یک سال معاملاتی)؛ سقف کل تاریخچه
# گمراه‌کننده است چون افت «جاری» را نشان نمی‌دهد (یافته‌ی ممیزی).
DRAWDOWN_WINDOW_DAYS = 252
# سقف رکوردهای خوانده‌شده برای سقف پنجره (جلوگیری از load کل جدول)
DRAWDOWN_MAX_POINTS = 300


@dataclass
class BuildOutcome:
    snapshot_id: str = ""
    captured_at: str = ""
    macro_regime: str = ""
    market_regime: str = ""
    confidence: float = 0.0
    signals: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "captured_at": self.captured_at,
            "macro_regime": self.macro_regime,
            "market_regime": self.market_regime,
            "confidence": self.confidence,
            "signals": self.signals,
        }


def _parse_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        out = json.loads(raw)
        return out if isinstance(out, list) else []
    except Exception:  # noqa: BLE001
        return []


class WorldStateBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- gather helpers ---
    def _latest_macro(self, indicator: str) -> list[MacroObservation]:
        stmt = (
            select(MacroObservation)
            .where(MacroObservation.indicator == indicator)
            .order_by(MacroObservation.period.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def _latest_market(self, symbol: str) -> MarketObservation | None:
        stmt = (
            select(MarketObservation)
            .where(MarketObservation.symbol == symbol)
            .order_by(MarketObservation.observed_at.desc())
        )
        return self.db.execute(stmt).scalars().first()

    def _spx_drawdown(self) -> float | None:
        """افت SPX از سقف پنجره‌ی اخیر (کسری مثبت؛ None یعنی داده‌ی ناکافی).

        - سقف فقط در ۲۵۲ روز منتهی به آخرین مشاهده جست‌وجو می‌شود.
        - حداکثر ۳۰۰ رکورد مرتب خوانده می‌شود (بدون load کل جدول).
        - کمتر از ۲ مقدار مثبت در پنجره → None (ناموجود، نه صفر جعلی).
        """
        latest = self._latest_market("SPX")
        if (
            latest is None
            or latest.value is None
            or latest.value <= 0
            or latest.observed_at is None
        ):
            return None
        cutoff = latest.observed_at - timedelta(days=DRAWDOWN_WINDOW_DAYS)
        stmt = (
            select(MarketObservation.value)
            .where(
                MarketObservation.symbol == "SPX",
                MarketObservation.value.is_not(None),
                MarketObservation.value > 0,
                MarketObservation.observed_at.is_not(None),
                MarketObservation.observed_at >= cutoff,
                MarketObservation.observed_at <= latest.observed_at,
            )
            .order_by(MarketObservation.observed_at.desc())
            .limit(DRAWDOWN_MAX_POINTS)
        )
        vals = [v for v in self.db.execute(stmt).scalars().all() if v and v > 0]
        if len(vals) < 2:
            return None
        peak = max(vals)
        if peak <= 0:
            return None
        return max(0.0, (peak - latest.value) / peak)

    @staticmethod
    def _yoy(values_desc: list[float | None]) -> float | None:
        """رشد سالانه از دو مشاهده‌ی آخر (مرتب نزولی دوره)."""
        vals = [v for v in values_desc[:2] if v not in (None, 0)]
        if len(vals) < 2 or not vals[1]:
            return None
        return (vals[0] - vals[1]) / abs(vals[1])

    @staticmethod
    def _country_values(
        rows: list[MacroObservation], prefer: str = "USA"
    ) -> list[float | None]:
        """مقادیر یک کشور واحد (ترجیح USA) تا ترکیب کشورها YoY را خراب نکند."""
        countries = [r.country for r in rows if r.country]
        pick = prefer if prefer in countries else (countries[0] if countries else None)
        return [r.value for r in rows if r.country == pick]

    # --- build ---
    def build(self, *, granularity: str = "daily") -> BuildOutcome:
        now = datetime.now(UTC)
        now_iso = now.isoformat()

        # 1) macro inputs
        gdp_rows = self._latest_macro("gdp")
        cpi_rows = self._latest_macro("inflation")
        liq_rows = self._latest_macro("liquidity")
        trade_rows = self._latest_macro("trade_balance")
        gdp_yoy = self._yoy(self._country_values(gdp_rows))
        liq_yoy = self._yoy(self._country_values(liq_rows))
        cpi_vals = self._country_values(cpi_rows)
        trade_vals = self._country_values(trade_rows)
        cpi_latest = cpi_vals[0] if cpi_vals and cpi_vals[0] is not None else None
        trade_latest = trade_vals[0] if trade_vals and trade_vals[0] is not None else None

        # 2) market inputs
        wti = self._latest_market("WTI")
        brent = self._latest_market("BRENT")
        tnx = self._latest_market("US10Y")
        drawdown = self._spx_drawdown()

        # 3) event/claim inputs
        events = list(self.db.execute(select(Event)).scalars().all())
        claims = list(self.db.execute(select(Claim)).scalars().all())
        n_events = len(events)
        surprises = [e.surprise for e in events if e.surprise is not None]
        avg_surprise = sum(surprises) / len(surprises) if surprises else None
        disputed = sum(1 for c in claims if c.verification_status in DISPUTED_STATUSES)
        disputed_share = (disputed / len(claims)) if claims else None

        def event_share(types: frozenset, topics: frozenset) -> float | None:
            if not events:
                return None
            hit = 0
            for e in events:
                if (e.event_type or "") in types:
                    hit += 1
                    continue
                for a in e.articles[:4]:
                    ts = {str(t).lower() for t in _parse_list(a.topics) if isinstance(t, str)}
                    if ts & topics:
                        hit += 1
                        break
            return hit / len(events)

        # 4) signals
        computed: dict[str, sig.Signal] = {
            "growth_pressure": sig.growth_pressure(gdp_yoy),
            "inflation_pressure": sig.inflation_pressure(cpi_latest),
            "liquidity": sig.liquidity(liq_yoy),
            "financial_stress": sig.financial_stress(
                tnx.value if tnx and tnx.value is not None else None, drawdown
            ),
            "geopolitical_risk": sig.geopolitical_risk(disputed_share, avg_surprise, n_events),
            "energy_risk": sig.energy_risk(
                wti.value if wti and wti.value is not None else None,
                brent.value if brent and brent.value is not None else None,
            ),
            "trade_risk": sig.trade_risk(trade_latest),
            "political_risk": sig.political_risk(
                event_share(sig.POLITICAL_TYPES, sig.POLITICAL_TOPICS), n_events
            ),
            "social_pressure": sig.social_pressure(
                event_share(sig.SOCIAL_TYPES, sig.SOCIAL_TOPICS), n_events
            ),
        }

        # 5) regimes + confidence
        macro_r = sig.macro_regime(
            computed["growth_pressure"].value, computed["inflation_pressure"].value
        )
        market_r = sig.market_regime(
            computed["financial_stress"].value, computed["liquidity"].value
        )
        confidence = round(
            sum(s.confidence for s in computed.values()) / len(computed), 3
        )

        # 6) persist
        meta = {
            name: {
                "value": round(s.value, 4),
                "timestamp": now_iso,
                "source": "worldstate_builder_v1",
                "method": s.method,
                "confidence": s.confidence,
            }
            for name, s in computed.items()
        }
        snapshot = WorldState(
            captured_at=now,
            granularity=granularity,
            macro_regime=macro_r,
            market_regime=market_r,
            value_metadata=json.dumps(meta, ensure_ascii=False),
            confidence=confidence,
            notes=f"build v1 from {len(gdp_rows)} gdp / {n_events} events / {len(claims)} claims",
        )
        for name, s in computed.items():
            setattr(snapshot, name, round(s.value, 4))
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)

        logger.info(
            "world-state built | macro=%s market=%s conf=%.3f",
            macro_r, market_r, confidence,
        )
        return BuildOutcome(
            snapshot_id=str(snapshot.id),
            captured_at=now_iso,
            macro_regime=macro_r,
            market_regime=market_r,
            confidence=confidence,
            signals={k: v["value"] for k, v in meta.items()},
        )
