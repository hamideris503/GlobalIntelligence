"""Self-evaluation service — اجرای چک‌ها و ثبت تاریخچه (Phase 39).

هر اجرا یک ردیف افزودنی در `self_evaluations` می‌سازد (تاریخچه‌ی سلامت).
بدون AI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.article import Article
from backend.database.models.claim import Claim
from backend.database.models.entity import EntityRelationship
from backend.database.models.evidence import Evidence
from backend.database.models.market import MarketObservation
from backend.database.models.memory import MemoryRecord
from backend.database.models.model_performance import ModelPerformance
from backend.database.models.self_evaluation import SelfEvaluation
from domains.selfeval import checks as ck

logger = get_logger(__name__)


@dataclass
class SelfEvalOutcome:
    evaluation_id: str = ""
    score: float = 0.0
    grade: str = "D"
    checks: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "evaluation_id": self.evaluation_id,
            "score": self.score,
            "grade": self.grade,
            "checks": self.checks,
        }


class SelfEvaluationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _count(self, model: object, *filters) -> int:  # type: ignore[valid-type]
        stmt = select(func.count()).select_from(model)
        for f in filters:
            stmt = stmt.where(f)
        return int(self.db.execute(stmt).scalars().one() or 0)

    def run(self) -> SelfEvalOutcome:
        now = datetime.now(UTC)
        results: list[ck.Check] = []

        n_articles = self._count(Article)
        n_done = self._count(Article, Article.classification_status == "done")
        results.append(ck.classification_check(n_done, n_articles))

        n_claims = self._count(Claim)
        covered = self.db.execute(
            select(func.count(func.distinct(Evidence.claim_id)))
        ).scalars().one() or 0
        results.append(ck.evidence_check(int(covered), n_claims))

        n_models = self._count(ModelPerformance)
        results.append(ck.forecast_check(n_models))

        latest_obs = self.db.execute(
            select(func.max(MarketObservation.observed_at))
        ).scalars().one()
        if latest_obs is not None and latest_obs.tzinfo is None:
            latest_obs = latest_obs.replace(tzinfo=UTC)
        hours = (
            (now - latest_obs).total_seconds() / 3600.0 if latest_obs else None
        )
        results.append(ck.freshness_check(hours))

        layers = {
            r for r in self.db.execute(
                select(MemoryRecord.layer).group_by(MemoryRecord.layer)
            ).scalars().all() if r
        }
        results.append(ck.memory_check(layers))

        n_rels = self._count(EntityRelationship)
        results.append(ck.graph_check(n_rels))

        score, grade = ck.overall(results)
        record = SelfEvaluation(
            score=score,
            grade=grade,
            checks=json.dumps([c.as_dict() for c in results], ensure_ascii=False),
            method="selfeval_v1",
            observed_at=now,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        logger.info("self-eval done | score=%.3f grade=%s", score, grade)
        return SelfEvalOutcome(
            evaluation_id=str(record.id),
            score=score,
            grade=grade,
            checks=[c.as_dict() for c in results],
        )
