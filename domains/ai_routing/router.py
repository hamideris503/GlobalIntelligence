"""Adaptive routing — امتیاز Provider از عملکرد ثبت‌شده (Phase 37).

قرارداد (v1, مستند و ثابت):
- نرخ موفقیت با هموارسازی لاپلاس: (successes+1)/(calls+2) تا نمونه‌های
  کوچک (۱/۱) بر نمونه‌های بزرگ (۹۹/۱۰۰) غلبه نکنند.
- ترتیب: success_rate نزولی، سپس calls نزولی، سپس میانگین تأخیر صعودی.
- Provider بی‌سابقه در انتهای زنجیره می‌ماند (ترتیب static حفظ می‌شود)؛
  mock فقط در MOCK_MODE معنا دارد و در production توسط gateway حذف می‌شود.
- خروجی `build_routes` مستقیماً به `AIGateway(routes=...)` تزریق می‌شود؛
  هیچ تغییری در منطق fallback/retry gateway لازم نیست.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ai.routing.router import Route
from backend.database.models.provider_run_stat import ProviderRunStat


@dataclass(frozen=True)
class ProviderScore:
    provider: str
    model: str
    calls: int
    success_rate: float
    avg_latency_ms: float | None

    def as_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "calls": self.calls,
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency_ms,
        }


def smoothed_rate(successes: int, calls: int) -> float:
    """نرخ موفقیت لاپلاس‌هموارشده."""
    return round((successes + 1) / (calls + 2), 4)


@dataclass
class RouteSuggestion:
    task: str
    providers: list[str] = field(default_factory=list)
    scores: list[ProviderScore] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "task": self.task,
            "providers": self.providers,
            "scores": [s.as_dict() for s in self.scores],
        }


@dataclass(frozen=True)
class _Agg:
    provider: str
    model: str
    calls: int = 0
    successes: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0


class AdaptiveRouter:
    """ساخت زنجیره‌ی تطبیقی از آمار ثبت‌شده."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        task: str,
        provider: str,
        model: str,
        success: bool,
        latency_ms: float | None = None,
        structured_ok: bool = False,
        period: str | None = None,
    ) -> ProviderRunStat:
        """ثبت یک اجرای task (upsert ماهانه، idempotent در جمع)."""
        from datetime import UTC, datetime

        period = period or datetime.now(UTC).strftime("%Y-%m")
        row = self.db.execute(
            select(ProviderRunStat).where(
                ProviderRunStat.provider == provider,
                ProviderRunStat.model == model,
                ProviderRunStat.task == task,
                ProviderRunStat.period == period,
            )
        ).scalar_one_or_none()
        if row is None:
            row = ProviderRunStat(
                provider=provider, model=model, task=task, period=period
            )
            self.db.add(row)
            self.db.flush()
        row.calls = (row.calls or 0) + 1
        if success:
            row.successes = (row.successes or 0) + 1
        else:
            row.failures = (row.failures or 0) + 1
        if latency_ms is not None:
            row.total_latency_ms = (row.total_latency_ms or 0.0) + latency_ms
        if structured_ok:
            row.structured_ok = (row.structured_ok or 0) + 1
        self.db.commit()
        self.db.refresh(row)
        return row

    def _stats(self, task: str) -> list[_Agg]:
        # تجمیع همه‌ی دوره‌ها برای هر (provider, model) — فقط خواندنی،
        # بدون mutate آبجکت‌های ORM (commit بعدی نباید ردیف‌ها را خراب کند).
        stmt = select(ProviderRunStat).where(ProviderRunStat.task == task)
        acc: dict[tuple[str, str], _Agg] = {}
        for row in self.db.execute(stmt).scalars().all():
            key = (row.provider, row.model)
            prev = acc.get(key)
            if prev is None:
                acc[key] = _Agg(
                    provider=row.provider,
                    model=row.model,
                    calls=row.calls or 0,
                    successes=row.successes or 0,
                    failures=row.failures or 0,
                    total_latency_ms=row.total_latency_ms or 0.0,
                )
            else:
                acc[key] = _Agg(
                    provider=prev.provider,
                    model=prev.model,
                    calls=prev.calls + (row.calls or 0),
                    successes=prev.successes + (row.successes or 0),
                    failures=prev.failures + (row.failures or 0),
                    total_latency_ms=prev.total_latency_ms + (row.total_latency_ms or 0.0),
                )
        return list(acc.values())

    def suggest(
        self, *, task: str, static_order: list[str] | None = None
    ) -> RouteSuggestion:
        """زنجیره‌ی پیشنهادی: اول باتجربه‌های موفق، سپس بی‌سابقه‌ها."""
        static_order = static_order or []
        scored: list[tuple[float, int, float, ProviderScore]] = []
        for agg in self._stats(task):
            calls = agg.calls
            if calls <= 0:
                continue
            rate = smoothed_rate(agg.successes, calls)
            avg = (
                round(agg.total_latency_ms / calls, 2)
                if agg.total_latency_ms > 0
                else float("inf")
            )
            scored.append(
                (
                    -rate,
                    -calls,
                    avg if avg != float("inf") else 1e12,
                    ProviderScore(
                        provider=agg.provider,
                        model=agg.model,
                        calls=calls,
                        success_rate=rate,
                        avg_latency_ms=None if avg == float("inf") else avg,
                    ),
                )
            )
        scored.sort(key=lambda t: (t[0], t[1], t[2]))
        ordered = [s.provider for _, _, _, s in scored]
        for name in static_order:
            if name not in ordered:
                ordered.append(name)
        return RouteSuggestion(
            task=task,
            providers=ordered,
            scores=[s for _, _, _, s in scored],
        )

    def build_routes(
        self, tasks: list[str], static_orders: dict[str, list[str]] | None = None
    ) -> dict[str, Route]:
        """دیکشنری Route آماده‌ی تزریق به AIGateway(routes=...)."""
        static_orders = static_orders or {}
        return {
            task: Route(
                role=task,
                providers=self.suggest(
                    task=task, static_order=static_orders.get(task)
                ).providers,
            )
            for task in tasks
        }
