"""Analogue Engine — یافتن وضعیت‌های تاریخی مشابه + پیامد بعدی (Phase 20).

مسیر: snapshot فعلی (یا مشخص) ↔ snapshotهای قدیمی‌تر (فاصله‌ی برداری)
      → رتبه‌بندی + واگرایی هر سیگنال + «بعدش چه شد» (snapshotهای بعدی و رویدادها).

- فقط خواندنی؛ بدون migration؛ بدون AI.
- آنالوگ باید قدیمی‌تر از وضعیت مرجع باشد (گذشته، نه آینده).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.enums import MemoryLayer
from backend.database.models.memory import MemoryRecord
from backend.database.models.world_state import WorldState
from domains.analogue.similarity import (
    SIGNAL_ORDER,
    cosine_distance,
    deltas,
    euclidean,
    similarity,
    to_vector,
)

logger = get_logger(__name__)


@dataclass
class AnalogueHit:
    snapshot_id: str
    captured_at: str
    distance: float
    similarity: float
    macro_regime: str | None
    market_regime: str | None
    deltas: dict[str, float]

    def as_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "captured_at": self.captured_at,
            "distance": self.distance,
            "similarity": self.similarity,
            "macro_regime": self.macro_regime,
            "market_regime": self.market_regime,
            "deltas": self.deltas,
        }


@dataclass
class AnalogueOutcome:
    reference_id: str
    metric: str
    hits: list[AnalogueHit] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "reference_id": self.reference_id,
            "metric": self.metric,
            "hits": [h.as_dict() for h in self.hits],
        }


@dataclass
class AftermathOutcome:
    analogue_id: str
    next_snapshots: list[dict] = field(default_factory=list)
    next_events: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "analogue_id": self.analogue_id,
            "next_snapshots": self.next_snapshots,
            "next_events": self.next_events,
        }


def _snapshot_signals(s: WorldState) -> dict:
    return {name: getattr(s, name) for name in SIGNAL_ORDER}


class AnalogueService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get(self, snapshot_id: str) -> WorldState | None:
        try:
            uid = UUID(snapshot_id)
        except ValueError:
            return None
        return self.db.get(WorldState, uid)

    def _latest(self) -> WorldState | None:
        stmt = select(WorldState).order_by(WorldState.captured_at.desc()).limit(1)
        return self.db.execute(stmt).scalars().first()

    def find_analogues(
        self,
        *,
        snapshot_id: str | None = None,
        top_k: int = 5,
        metric: str = "euclidean",
    ) -> AnalogueOutcome:
        if metric not in ("euclidean", "cosine"):
            raise ValueError(f"unknown metric: {metric}")
        ref = self._get(snapshot_id) if snapshot_id else self._latest()
        if ref is None:
            raise LookupError("reference snapshot not found")
        if ref.captured_at is None:
            raise ValueError("reference snapshot has no captured_at")

        dist_fn = euclidean if metric == "euclidean" else cosine_distance
        ref_vec = to_vector(_snapshot_signals(ref))
        stmt = (
            select(WorldState)
            .where(WorldState.captured_at < ref.captured_at)
            .order_by(WorldState.captured_at.desc())
        )
        hits: list[AnalogueHit] = []
        for s in self.db.execute(stmt).scalars().all():
            if s.captured_at is None:
                continue
            vec = to_vector(_snapshot_signals(s))
            dist = round(dist_fn(ref_vec, vec), 4)
            hits.append(
                AnalogueHit(
                    snapshot_id=str(s.id),
                    captured_at=s.captured_at.isoformat(),
                    distance=dist,
                    similarity=similarity(dist, metric),
                    macro_regime=s.macro_regime,
                    market_regime=s.market_regime,
                    deltas=deltas(ref_vec, vec),
                )
            )
        hits.sort(key=lambda h: h.distance)
        logger.info(
            "analogues found | ref=%s metric=%s candidates=%d",
            ref.id, metric, len(hits),
        )
        return AnalogueOutcome(
            reference_id=str(ref.id), metric=metric, hits=hits[:top_k]
        )

    def aftermath(
        self, *, analogue_id: str, limit: int = 5
    ) -> AftermathOutcome:
        """«بعد از آنالوگ چه شد»: snapshotهای بعدی + رویدادهای حافظه‌ی بعدی."""
        analogue = self._get(analogue_id)
        if analogue is None:
            raise LookupError("analogue snapshot not found")
        if analogue.captured_at is None:
            raise ValueError("analogue snapshot has no captured_at")

        next_states = list(
            self.db.execute(
                select(WorldState)
                .where(WorldState.captured_at > analogue.captured_at)
                .order_by(WorldState.captured_at.asc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        next_events = list(
            self.db.execute(
                select(MemoryRecord)
                .where(
                    MemoryRecord.layer == MemoryLayer.event.value,
                    MemoryRecord.observed_at > analogue.captured_at,
                )
                .order_by(MemoryRecord.observed_at.asc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return AftermathOutcome(
            analogue_id=str(analogue.id),
            next_snapshots=[
                {
                    "snapshot_id": str(s.id),
                    "captured_at": s.captured_at.isoformat() if s.captured_at else None,
                    "macro_regime": s.macro_regime,
                    "market_regime": s.market_regime,
                }
                for s in next_states
            ],
            next_events=[
                {
                    "record_id": str(r.id),
                    "title": r.title,
                    "observed_at": r.observed_at.isoformat() if r.observed_at else None,
                    "importance": r.importance,
                }
                for r in next_events
            ],
        )
