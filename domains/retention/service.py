"""Retention service — dry-run + disk monitoring (Stage 100).

هیچ حذف واقعی انجام نمی‌شود. dry-run فقط candidateهای پیشنهادی را برمی‌گرداند.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.article_dispatch import ArticleDispatch
from backend.database.models.document import Document
from backend.database.models.job import JobRun
from backend.database.models.market import MarketObservation
from domains.retention.policy import PROTECTED_ENTITIES, RetentionPolicy

logger = get_logger(__name__)


@dataclass
class CandidateGroup:
    entity: str
    count: int = 0
    approx_bytes: int = 0
    sample_ids: list[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class RetentionDryRun:
    policy: dict[str, Any]
    candidates: list[dict[str, Any]] = field(default_factory=list)
    protected: list[str] = field(default_factory=list)
    total_candidates: int = 0
    approx_freed_bytes: int = 0
    disk: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "candidates": self.candidates,
            "protected": self.protected,
            "total_candidates": self.total_candidates,
            "approx_freed_bytes": self.approx_freed_bytes,
            "disk": self.disk,
            "errors": self.errors,
            "note": "dry-run only; no deletion performed",
        }


def disk_status(path: str = ".") -> dict[str, Any]:
    """پایش دیسک: total/used/free/percent + هشدار."""
    try:
        du = shutil.disk_usage(path)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    percent = (du.used / du.total * 100.0) if du.total else 0.0
    return {
        "path": os.path.abspath(path),
        "total": du.total,
        "used": du.used,
        "free": du.free,
        "used_percent": round(percent, 2),
    }


class RetentionService:
    def __init__(self, db: Session, policy: RetentionPolicy | None = None) -> None:
        self.db = db
        self.policy = policy or RetentionPolicy()

    def _cutoff(self, days: int) -> datetime:
        return datetime.now(UTC) - timedelta(days=days)

    def dry_run(self) -> RetentionDryRun:
        result = RetentionDryRun(
            policy={
                "document_min_age_days": self.policy.document_min_age_days,
                "market_observation_min_age_days": self.policy.market_observation_min_age_days,
                "job_run_min_age_days": self.policy.job_run_min_age_days,
                "dispatch_terminal_min_age_days": self.policy.dispatch_terminal_min_age_days,
                "batch_size": self.policy.batch_size,
            },
            protected=sorted(PROTECTED_ENTITIES),
            disk=disk_status(),
        )
        try:
            # Documents (raw) older than threshold
            cutoff = self._cutoff(self.policy.document_min_age_days)
            docs = self.db.execute(
                select(Document).where(Document.created_at < cutoff)
            ).scalars().all()
            # only those without protected downstream? For safety, only count; no deletion
            group = CandidateGroup(
                entity="document",
                count=len(docs),
                approx_bytes=sum(len((d.raw_text or "").encode("utf-8")) for d in docs),
                sample_ids=[str(d.id) for d in docs[:10]],
                reason=f"created_at < {cutoff.date().isoformat()}",
            )
            result.candidates.append(group.__dict__)
            result.total_candidates += group.count
            result.approx_freed_bytes += group.approx_bytes

            # Market observations older than threshold
            cutoff = self._cutoff(self.policy.market_observation_min_age_days)
            mos = self.db.execute(
                select(MarketObservation).where(MarketObservation.observed_at < cutoff)
            ).scalars().all()
            group = CandidateGroup(
                entity="market_observation",
                count=len(mos),
                approx_bytes=0,
                sample_ids=[str(m.id) for m in mos[:10]],
                reason=f"observed_at < {cutoff.date().isoformat()}",
            )
            result.candidates.append(group.__dict__)
            result.total_candidates += group.count

            # Job runs older than threshold
            cutoff = self._cutoff(self.policy.job_run_min_age_days)
            jobs = self.db.execute(
                select(JobRun).where(JobRun.started_at < cutoff)
            ).scalars().all()
            group = CandidateGroup(
                entity="job_run",
                count=len(jobs),
                approx_bytes=0,
                sample_ids=[str(j.id) for j in jobs[:10]],
                reason=f"started_at < {cutoff.date().isoformat()}",
            )
            result.candidates.append(group.__dict__)
            result.total_candidates += group.count

            # Terminal article_dispatches older than threshold
            cutoff = self._cutoff(self.policy.dispatch_terminal_min_age_days)
            disp = self.db.execute(
                select(ArticleDispatch).where(
                    ArticleDispatch.status == "terminal",
                    ArticleDispatch.updated_at < cutoff,
                )
            ).scalars().all()
            group = CandidateGroup(
                entity="article_dispatch_terminal",
                count=len(disp),
                approx_bytes=0,
                sample_ids=[str(d.id) for d in disp[:10]],
                reason=f"terminal & updated_at < {cutoff.date().isoformat()}",
            )
            result.candidates.append(group.__dict__)
            result.total_candidates += group.count
        except Exception as exc:  # noqa: BLE001
            logger.warning("retention dry-run error: %s", exc)
            result.errors.append(f"{type(exc).__name__}: {exc}")
        return result

    def disk_alert_needed(self) -> bool:
        st = disk_status()
        if "error" in st:
            return False
        return st["used_percent"] >= self.policy.disk_warn_percent