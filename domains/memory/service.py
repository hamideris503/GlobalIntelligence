"""Historical Memory Service — بایگانی رویدادها/حالت‌ها/داده‌های خام (Phase 19).

لایه‌های فعال Phase 19: raw (مقالات مهم)، event (رویدادهای مهم)، state (snapshotها).
لایه‌های forecast/outcome/model/decision برای فازهای بعد رزرو است.

قوانین گزینش (قطعی و مستند، v1):
- event: امتیاز = 0.5*surprise + 0.5*min(1, article_count/5)؛ آستانه‌ی 0.3
- raw: مقالات با importance >= 7 (مقیاس ۱..۱۰ طبقه‌بندی)
- state: همه‌ی snapshotهای WorldState (هر snapshot یک حافظه است)

پرس‌وجوی کلیدی: timeline(as_of) — «در زمان T چه می‌دانستیم؟»
بدون AI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.enums import MemoryLayer
from backend.database.models.article import Article
from backend.database.models.event import Event
from backend.database.models.memory import MemoryRecord
from backend.database.models.world_state import WorldState

logger = get_logger(__name__)

EVENT_SCORE_THRESHOLD = 0.3
RAW_IMPORTANCE_THRESHOLD = 7


@dataclass
class ArchiveOutcome:
    raw_archived: int = 0
    events_archived: int = 0
    states_archived: int = 0
    duplicates: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "raw_archived": self.raw_archived,
            "events_archived": self.events_archived,
            "states_archived": self.states_archived,
            "duplicates": self.duplicates,
            "failed": self.failed,
            "errors": self.errors,
        }


def event_score(surprise: float | None, article_count: int) -> float:
    """امتیاز اهمیت رویداد در [0, 1]."""
    s = max(0.0, min(1.0, surprise if surprise is not None else 0.0))
    return round(0.5 * s + 0.5 * min(1.0, article_count / 5.0), 4)


class HistoricalMemoryService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _store(
        self,
        *,
        layer: str,
        ref_type: str,
        ref_id: str,
        title: str | None,
        summary: str | None,
        importance: float | None,
        observed_at: datetime | None,
        meta: dict,
        outcome: ArchiveOutcome,
        counter: str,
    ) -> None:
        existing = self.db.execute(
            select(MemoryRecord).where(
                MemoryRecord.layer == layer,
                MemoryRecord.ref_type == ref_type,
                MemoryRecord.ref_id == ref_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            outcome.duplicates += 1
            return
        now = datetime.now(UTC)
        self.db.add(
            MemoryRecord(
                layer=layer,
                ref_type=ref_type,
                ref_id=ref_id,
                title=(title or "")[:512],
                summary=summary,
                importance=importance,
                observed_at=observed_at or now,
                recorded_at=now,
                record_metadata=json.dumps(meta, ensure_ascii=False),
            )
        )
        self.db.flush()
        setattr(outcome, counter, getattr(outcome, counter) + 1)

    def archive_events(self, *, limit: int = 200) -> ArchiveOutcome:
        outcome = ArchiveOutcome()
        events = list(
            self.db.execute(select(Event).order_by(Event.created_at.desc()).limit(limit))
            .scalars()
            .all()
        )
        for e in events:
            try:
                n_articles = len(e.articles)
                score = event_score(e.surprise, n_articles)
                if score < EVENT_SCORE_THRESHOLD:
                    continue
                self._store(
                    layer=MemoryLayer.event.value,
                    ref_type="event",
                    ref_id=str(e.id),
                    title=e.action,
                    summary=e.action,
                    importance=score,
                    observed_at=e.occurred_at or e.created_at,
                    meta={
                        "method": "event_score_v1",
                        "surprise": e.surprise,
                        "article_count": n_articles,
                        "event_type": e.event_type,
                    },
                    outcome=outcome,
                    counter="events_archived",
                )
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
        self.db.commit()
        return outcome

    def archive_states(self, *, limit: int = 200) -> ArchiveOutcome:
        outcome = ArchiveOutcome()
        states = list(
            self.db.execute(
                select(WorldState).order_by(WorldState.captured_at.desc()).limit(limit)
            )
            .scalars()
            .all()
        )
        for s in states:
            try:
                self._store(
                    layer=MemoryLayer.state.value,
                    ref_type="world_state",
                    ref_id=str(s.id),
                    title=f"WorldState {s.macro_regime}/{s.market_regime}",
                    summary=s.notes,
                    importance=s.confidence,
                    observed_at=s.captured_at or s.created_at,
                    meta={
                        "method": "snapshot_v1",
                        "macro_regime": s.macro_regime,
                        "market_regime": s.market_regime,
                    },
                    outcome=outcome,
                    counter="states_archived",
                )
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
        self.db.commit()
        return outcome

    def archive_raw(self, *, limit: int = 200) -> ArchiveOutcome:
        outcome = ArchiveOutcome()
        articles = list(
            self.db.execute(
                select(Article)
                .where(Article.importance >= RAW_IMPORTANCE_THRESHOLD)
                .order_by(Article.importance.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        for a in articles:
            try:
                self._store(
                    layer=MemoryLayer.raw.value,
                    ref_type="article",
                    ref_id=str(a.id),
                    title=a.title,
                    summary=a.summary,
                    importance=float(a.importance) / 10.0 if a.importance else None,
                    observed_at=a.published_at or a.retrieved_at or a.created_at,
                    meta={"method": "importance_threshold_v1", "importance": a.importance},
                    outcome=outcome,
                    counter="raw_archived",
                )
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
        self.db.commit()
        return outcome

    def archive_all(self, *, limit: int = 200) -> ArchiveOutcome:
        total = ArchiveOutcome()
        for res in (
            self.archive_events(limit=limit),
            self.archive_states(limit=limit),
            self.archive_raw(limit=limit),
        ):
            total.raw_archived += res.raw_archived
            total.events_archived += res.events_archived
            total.states_archived += res.states_archived
            total.duplicates += res.duplicates
            total.failed += res.failed
            total.errors.extend(res.errors)
        logger.info("memory archive done | %s", total.as_dict())
        return total

    def timeline(
        self,
        *,
        as_of: datetime,
        layer: str | None = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        """رکوردهای دانسته‌شده تا زمان as_of (Point-in-Time)."""
        stmt = (
            select(MemoryRecord)
            .where(MemoryRecord.observed_at <= as_of)
            .order_by(MemoryRecord.observed_at.desc())
            .limit(limit)
        )
        if layer:
            stmt = stmt.where(MemoryRecord.layer == layer)
        return list(self.db.execute(stmt).scalars().all())

    def stats(self) -> dict[str, int]:
        stmt = select(MemoryRecord.layer, func.count()).group_by(MemoryRecord.layer)
        return {layer: count for layer, count in self.db.execute(stmt).all()}
