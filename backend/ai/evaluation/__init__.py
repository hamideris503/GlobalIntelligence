# ============================================================
# ai.evaluation — ثبت و ارزیابی عملکرد مدل‌ها
# ============================================================
"""
در Phase 5 فقط ساختار پایه نگهداری می‌شود؛ ثبت واقعی در Phase 36+.

برای هر فراخوانی AI باید قابل ثبت باشد:
task, model, prompt_version, accuracy, latency, failure_rate,
cost_estimate, structured_output_success.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class ModelRunRecord:
    task: str
    provider: str
    model: str
    prompt_version: str
    latency_ms: float | None = None
    success: bool = True
    error_kind: str | None = None
    cost_estimate: float | None = None
    structured_output_success: bool | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
