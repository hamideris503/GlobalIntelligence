"""Retention policy — قواعد نگهداری و حذف (Stage 100).

- موجودیت‌های محافظت‌شده (هرگز حذف نمی‌شوند): event, claim, evidence,
  forecast ledger, outcome, audit, AI logs, replay records.
- موجودیت‌های قابل بررسی (candidate): raw Document قدیمی، MarketObservation قدیمی،
  JobRun قدیمی، ArticleDispatch terminal قدیمی.
- هیچ حذف واقعی در این نسخه انجام نمی‌شود (dry-run).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# موجودیت‌هایی که هرگز نباید حذف شوند
PROTECTED_ENTITIES: frozenset[str] = frozenset(
    {
        "event",
        "claim",
        "evidence",
        "forecast",
        "outcome",
        "audit",
        "ai_log",
        "replay",
        "memory_record",
        "recommendation",
        "risk_assessment",
        "transmission_assessment",
        "world_state",
        "narrative",
        "macro_assessment",
        "geopolitical_assessment",
        "social_assessment",
        "alert",
        "alert_rule",
    }
)

# موجودیت‌های قابل candidate
CANDIDATE_ENTITIES: tuple[str, ...] = (
    "document",
    "market_observation",
    "job_run",
    "article_dispatch_terminal",
)


@dataclass
class RetentionPolicy:
    # سن (روز) پس از آن candidate می‌شود
    document_min_age_days: int = 90
    market_observation_min_age_days: int = 180
    job_run_min_age_days: int = 30
    dispatch_terminal_min_age_days: int = 30
    # آستانهٔ دیسک برای هشدار (درصد)
    disk_warn_percent: float = 70.0
    disk_critical_percent: float = 85.0
    # هیسترزیس
    hysteresis_percent: float = 5.0
    # حداکثر ردیف در یک batch dry-run
    batch_size: int = 500
    # فیلدهایی که باید حفظ شوند
    preserve_fields: tuple[str, ...] = field(
        default_factory=lambda: ("hash", "content_hash", "source_id")
    )

    def is_protected(self, entity: str) -> bool:
        return entity in PROTECTED_ENTITIES

    def candidate_min_age(self, entity: str) -> int | None:
        mapping = {
            "document": self.document_min_age_days,
            "market_observation": self.market_observation_min_age_days,
            "job_run": self.job_run_min_age_days,
            "article_dispatch_terminal": self.dispatch_terminal_min_age_days,
        }
        return mapping.get(entity)