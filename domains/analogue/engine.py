"""Analogue Engine — یافتن وضعیت‌های تاریخی مشابه + پیامد بعدی (Phase 20, اصلاح ممیزی).

مسیر: snapshot فعلی (یا مشخص) ↔ snapshotهای قدیمی‌تر (فاصله‌ی برداری)
      → رتبه‌بندی + واگرایی هر سیگنال + «بعدش چه شد» (snapshotهای بعدی و رویدادها).

قوانین پوشش داده (ممیزی):
- هر بُعد فقط وقتی مقایسه می‌شود که در **هر دو** snapshot معتبر باشد:
  ورودی metadata موجود، method != "no_data"، و confidence >= 0.3.
- نبود ورودی metadata = بُعد نامعتبر (strict؛ «ناموجود» هرگز «خنثی واقعی»
  فرض نمی‌شود).
- فاصله‌ی اقلیدسی به معادل تمام‌بعدی نرمال می‌شود تا پوشش‌های متفاوت
  منصفانه مقایسه شوند.
- هر hit اعلام می‌کند روی چند بُعد مقایسه شده (compared_dims/coverage)؛
  مرجع با کمتر از MIN_VALID_DIMS بُعد معتبر → خطای صریح (ساختگی نساز).

- فقط خواندنی؛ بدون migration؛ بدون AI.
- آنالوگ باید قدیمی‌تر از وضعیت مرجع باشد (گذشته، نه آینده).
"""
from __future__ import annotations

import json
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
    euclidean,
    masked_deltas,
    normalize_euclidean,
    similarity,
    to_vector,
)

logger = get_logger(__name__)

# حداقل confidence برای اینکه یک بُعد «قابل اتکا» شمرده شود
VALID_CONFIDENCE_THRESHOLD = 0.3
# حداقل ابعاد معتبر مشترک برای مقایسه‌ی معنادار
MIN_VALID_DIMS = 3


@dataclass
class AnalogueHit:
    snapshot_id: str
    captured_at: str
    distance: float
    similarity: float
    macro_regime: str | None
    market_regime: str | None
    deltas: dict[str, float]
    compared_dims: int
    coverage: float

    def as_dict(self) -> dict:
        return {
            "snapshot_id": self.snapshot_id,
            "captured_at": self.captured_at,
            "distance": self.distance,
            "similarity": self.similarity,
            "macro_regime": self.macro_regime,
            "market_regime": self.market_regime,
            "deltas": self.deltas,
            "compared_dims": self.compared_dims,
            "coverage": self.coverage,
        }


@dataclass
class AnalogueOutcome:
    reference_id: str
    metric: str
    valid_dims: int
    min_valid_dims: int
    hits: list[AnalogueHit] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "reference_id": self.reference_id,
            "metric": self.metric,
            "valid_dims": self.valid_dims,
            "min_valid_dims": self.min_valid_dims,
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


def _snapshot_meta(s: WorldState) -> dict:
    """متادیتای هر سیگنال از value_metadata (نامعتبر → {})."""
    try:
        meta = json.loads(s.value_metadata or "{}")
    except Exception:  # noqa: BLE001
        return {}
    return meta if isinstance(meta, dict) else {}


def _is_valid_dim(entry: object) -> bool:
    """بُعد معتبر: ورودی موجود، غیر-no_data، و confidence کافی."""
    if not isinstance(entry, dict):
        return False
    if entry.get("method") == "no_data":
        return False
    try:
        conf = float(entry.get("confidence", 0.0))
    except (TypeError, ValueError):
        return False
    return conf >= VALID_CONFIDENCE_THRESHOLD


def valid_dims(meta: dict) -> list[str]:
    """نام ابعاد معتبر یک snapshot به ترتیب ثابت."""
    return [name for name in SIGNAL_ORDER if _is_valid_dim(meta.get(name))]


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

        ref_meta = _snapshot_meta(ref)
        ref_valid = valid_dims(ref_meta)
        if len(ref_valid) < MIN_VALID_DIMS:
            raise ValueError(
                f"reference has only {len(ref_valid)} valid dims "
                f"(minimum {MIN_VALID_DIMS}); refusing to fabricate similarity"
            )

        ref_vec_full = to_vector(_snapshot_signals(ref))
        ref_idx = {name: i for i, name in enumerate(SIGNAL_ORDER)}
        dist_is_euclidean = metric == "euclidean"
        stmt = (
            select(WorldState)
            .where(WorldState.captured_at < ref.captured_at)
            .order_by(WorldState.captured_at.desc())
        )
        hits: list[AnalogueHit] = []
        skipped = 0
        for s in self.db.execute(stmt).scalars().all():
            if s.captured_at is None:
                continue
            common = [n for n in ref_valid if n in valid_dims(_snapshot_meta(s))]
            if len(common) < MIN_VALID_DIMS:
                skipped += 1
                continue
            cand_vec_full = to_vector(_snapshot_signals(s))
            ref_sub = [ref_vec_full[ref_idx[n]] for n in common]
            cand_sub = [cand_vec_full[ref_idx[n]] for n in common]
            if dist_is_euclidean:
                raw = euclidean(ref_sub, cand_sub)
                dist = round(normalize_euclidean(raw, len(common)), 4)
            else:
                dist = round(cosine_distance(ref_sub, cand_sub), 4)
            coverage = round(len(common) / len(SIGNAL_ORDER), 3)
            hits.append(
                AnalogueHit(
                    snapshot_id=str(s.id),
                    captured_at=s.captured_at.isoformat(),
                    distance=dist,
                    similarity=similarity(dist, metric),
                    macro_regime=s.macro_regime,
                    market_regime=s.market_regime,
                    deltas=masked_deltas(common, ref_sub, cand_sub),
                    compared_dims=len(common),
                    coverage=coverage,
                )
            )
        hits.sort(key=lambda h: h.distance)
        logger.info(
            "analogues found | ref=%s metric=%s candidates=%d skipped=%d",
            ref.id, metric, len(hits), skipped,
        )
        return AnalogueOutcome(
            reference_id=str(ref.id),
            metric=metric,
            valid_dims=len(ref_valid),
            min_valid_dims=MIN_VALID_DIMS,
            hits=hits[:top_k],
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
