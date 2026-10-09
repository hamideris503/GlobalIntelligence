"""Social Engine — تحلیل فضای اجتماعی موضوعات و کشورها (Phase 23).

مسیر: articles طبقه‌بندی‌شده (topics/sentiment/stance/country)
      → گروه‌بندی قلمرو (topic|country) → mood قطعی → upsert ماهانه.

- idempotent بر اساس UniqueConstraint (scope_type, scope, period).
- مقالات بدون topic/country در قلمروی مربوط نادیده گرفته می‌شوند (نه حدس).
- بدون AI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.article import Article
from backend.database.models.social_assessment import SocialAssessment
from domains.society.analytics import mood
from domains.worldstate.signals import SOCIAL_TOPICS

logger = get_logger(__name__)


@dataclass
class SocialOutcome:
    scopes_analyzed: int = 0
    stored: int = 0
    duplicates: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "scopes_analyzed": self.scopes_analyzed,
            "stored": self.stored,
            "duplicates": self.duplicates,
            "skipped": self.skipped,
            "failed": self.failed,
            "errors": self.errors,
        }


def _parse_topics(raw: str | None) -> set[str]:
    if not raw:
        return set()
    try:
        out = json.loads(raw)
    except Exception:  # noqa: BLE001
        return set()
    return {str(t).strip().lower() for t in out if isinstance(t, str) and str(t).strip()}


class SocialEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def analyze_all(self, *, period: str | None = None) -> SocialOutcome:
        outcome = SocialOutcome()
        period = period or datetime.now(UTC).strftime("%Y-%m")

        articles = list(
            self.db.execute(
                select(Article).where(Article.classification_status == "done")
            )
            .scalars()
            .all()
        )
        # قلمروها: هر topic یک قلمرو + هر country یک قلمرو
        buckets: dict[tuple[str, str], list[Article]] = {}
        for a in articles:
            for t in _parse_topics(a.topics):
                buckets.setdefault(("topic", t), []).append(a)
            if a.country and a.country.strip():
                buckets.setdefault(("country", a.country.strip().upper()), []).append(a)

        if not buckets:
            outcome.skipped += 1
            return outcome

        for (scope_type, scope), arts in sorted(buckets.items()):
            try:
                stats = mood(
                    [a.sentiment for a in arts],
                    [_parse_topics(a.topics) for a in arts],
                    [a.stance for a in arts],
                    SOCIAL_TOPICS,
                )
                if stats is None:
                    outcome.skipped += 1
                    continue
                outcome.scopes_analyzed += 1
                existing = self.db.execute(
                    select(SocialAssessment).where(
                        SocialAssessment.scope_type == scope_type,
                        SocialAssessment.scope == scope,
                        SocialAssessment.period == period,
                    )
                ).scalar_one_or_none()
                payload = {
                    "avg_sentiment": stats.avg_sentiment,
                    "article_count": stats.article_count,
                    "unrest_share": stats.unrest_share,
                    "stance_mix": json.dumps(stats.stance_mix, ensure_ascii=False),
                    "method": stats.method,
                    "confidence": stats.confidence,
                    "observed_at": datetime.now(UTC),
                }
                if existing is not None:
                    for k, v in payload.items():
                        setattr(existing, k, v)
                    outcome.duplicates += 1
                else:
                    self.db.add(
                        SocialAssessment(
                            scope_type=scope_type, scope=scope, period=period, **payload
                        )
                    )
                    self.db.flush()
                    outcome.stored += 1
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning(
                    "society analyze failed | %s=%s err=%s", scope_type, scope, exc
                )
        self.db.commit()
        logger.info("society analyze done | %s", outcome.as_dict())
        return outcome
