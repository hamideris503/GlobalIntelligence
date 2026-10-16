"""Debate context pack — بسته‌ی زمینه‌ی ثابت و مشترک (Point-in-Time).

برای هر debate یک بسته ساخته می‌شود و hash آن ذخیره می‌شود تا بازتولیدپذیر باشد.
قاعده‌ی Point-in-Time: هیچ داده‌ای با زمان انتشار بعد از as_of وارد نمی‌شود.
اگر شواهد کافی نبود، insufficient_reason تنظیم می‌شود (نه حدس).
"""
from __future__ import annotations

import hashlib
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
from domains.forecast.baselines import METHODS

logger = get_logger(__name__)

MAX_POINTS = 90


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _pct(new: float | None, old: float | None) -> float | None:
    if new is None or old is None or old == 0:
        return None
    return round((new - old) / abs(old) * 100.0, 2)


@dataclass
class ContextPack:
    """بسته‌ی زمینه + hash."""

    target: str
    target_date: datetime
    as_of: datetime
    reference_price: float | None
    reference_at: str | None
    prices: list[dict] = field(default_factory=list)
    changes_pct: dict = field(default_factory=dict)
    baselines: dict = field(default_factory=dict)
    world_state: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)  # ref_id: E1..
    claims: list[dict] = field(default_factory=list)  # ref_id: C1..
    macro: list[dict] = field(default_factory=list)
    insufficient_reason: str | None = None
    context_hash: str = ""

    def valid_refs(self) -> set[str]:
        return {e["ref_id"] for e in self.events} | {c["ref_id"] for c in self.claims}


def _market_prices(db: Session, symbol: str, as_of: datetime) -> list[tuple[datetime, float]]:
    rows = db.execute(
        select(MarketObservation)
        .where(
            MarketObservation.symbol == symbol,
            MarketObservation.value.is_not(None),
            MarketObservation.observed_at.is_not(None),
        )
        .order_by(MarketObservation.observed_at.asc())
    ).scalars().all()
    out = []
    for r in rows:
        obs = _aware(r.observed_at)
        if obs is not None and obs <= as_of and r.value is not None:
            out.append((obs, float(r.value)))
    return out[-MAX_POINTS:]


def build_context_pack(
    db: Session,
    *,
    target: str,
    horizon_days: int,
    max_events: int = 15,
    as_of: datetime | None = None,
) -> ContextPack:
    now = _aware(as_of) or datetime.now(UTC)
    assert now is not None
    parts = target.split(":")
    if len(parts) != 2 or parts[0] != "market" or not parts[1]:
        return ContextPack(
            target=target, target_date=now, as_of=now,
            reference_price=None, reference_at=None,
            insufficient_reason=f"unsupported target {target!r} (only market:{{symbol}})",
        )
    symbol = parts[1]
    target_date = now.replace(microsecond=0) + timedelta(days=horizon_days)

    prices = _market_prices(db, symbol, now)
    if not prices:
        return ContextPack(
            target=target, target_date=target_date, as_of=now,
            reference_price=None, reference_at=None,
            insufficient_reason=f"no price history for {symbol} as of {now.isoformat()}",
        )
    ref_dt, ref_price = prices[-1]
    closes = [p for _, p in prices]

    def _past(days: int) -> float | None:
        cutoff = ref_dt.timestamp() - days * 86400
        for dt, v in reversed(prices[:-1]):
            if dt.timestamp() <= cutoff:
                return v
        return closes[0] if closes else None

    changes = {
        "d1": _pct(ref_price, _past(1)),
        "d7": _pct(ref_price, _past(7)),
        "d30": _pct(ref_price, _past(30)),
    }
    baselines_out: dict[str, dict] = {}
    for name, fn in METHODS.items():
        try:
            kwargs = {"steps": 1} if name == "random_walk" else {}
            res = fn(closes, **kwargs)  # type: ignore[call-arg]
            if res is not None:
                baselines_out[name] = {
                    "expected_value": res.expected_value,
                    "interval_low": res.interval_low,
                    "interval_high": res.interval_high,
                    "confidence": res.confidence,
                }
        except Exception:  # noqa: BLE001
            continue

    ws = db.execute(
        select(WorldState).order_by(WorldState.captured_at.desc()).limit(1)
    ).scalars().first()
    world: dict = {}
    if ws is not None:
        for k in ("macro_regime", "market_regime", "growth_pressure",
                  "inflation_pressure", "liquidity", "financial_stress",
                  "geopolitical_risk", "energy_risk", "trade_risk",
                  "political_risk", "social_pressure"):
            world[k] = getattr(ws, k, None)

    # رویدادهای مرتبط (Point-in-Time) — مرتبط = اثر روی symbol یا بدون فیلتر دارایی
    ev_rows = db.execute(
        select(Event).order_by(Event.occurred_at.desc()).limit(max_events * 3)
    ).scalars().all()
    events: list[dict] = []
    for ev in ev_rows:
        occ = _aware(ev.occurred_at)
        if occ is not None and occ > now:
            continue
        try:
            assets = json.loads(ev.affected_assets or "[]")
        except Exception:  # noqa: BLE001
            assets = []
        if assets and symbol not in assets:
            continue
        try:
            actors = json.loads(ev.actors or "[]")
        except Exception:  # noqa: BLE001
            actors = []
        events.append({
            "ref_id": f"E{len(events) + 1}",
            "event_id": str(ev.id),
            "event_type": ev.event_type,
            "action": (ev.action or "")[:300],
            "occurred_at": occ.isoformat() if occ else None,
            "actors": actors[:6],
            "surprise": ev.surprise,
        })
        if len(events) >= max_events:
            break

    event_ids = {e["event_id"] for e in events}
    cl_rows = db.execute(select(Claim).limit(200)).scalars().all()
    claims: list[dict] = []
    for cl in cl_rows:
        if cl.event_id is not None and str(cl.event_id) not in event_ids:
            continue
        claims.append({
            "ref_id": f"C{len(claims) + 1}",
            "claim_id": str(cl.id),
            "text": f"{cl.subject or ''} {cl.predicate or ''} {cl.object or ''}".strip()[:300],
            "verification_status": cl.verification_status,
            "independent_sources": cl.independent_source_count,
            "supporting_sources": cl.supporting_source_count,
        })
        if len(claims) >= max_events:
            break

    # داده‌ی کلان مرتبط (آخرین هر شاخص، Point-in-Time ندارد چون دوره‌ای است)
    macro_rows = db.execute(select(MacroObservation)).scalars().all()
    macro_latest: dict[tuple, dict] = {}
    for r in macro_rows:
        key = (r.indicator, r.country)
        if key not in macro_latest or str(r.period) > str(macro_latest[key]["period"]):
            macro_latest[key] = {
                "indicator": r.indicator, "country": r.country,
                "period": r.period, "value": r.value, "unit": r.unit,
            }
    macro = sorted(macro_latest.values(), key=lambda d: str(d["indicator"]))[:20]

    pack = ContextPack(
        target=target, target_date=target_date, as_of=now,
        reference_price=ref_price, reference_at=ref_dt.isoformat(),
        prices=[{"t": dt.isoformat(), "v": v} for dt, v in prices[-30:]],
        changes_pct=changes, baselines=baselines_out, world_state=world,
        events=events, claims=claims, macro=macro,
    )
    if len(prices) < 5 and not events:
        pack.insufficient_reason = (
            f"thin evidence for {symbol}: {len(prices)} prices, 0 events"
        )
    blob = json.dumps({
        "target": pack.target, "as_of": now.isoformat(), "ref": ref_price,
        "closes": closes, "events": events, "claims": claims,
    }, ensure_ascii=False, sort_keys=True, default=str)
    pack.context_hash = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return pack
