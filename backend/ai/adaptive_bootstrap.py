"""Adaptive routing bootstrap (F-15) — اعمال خودکار زنجیره‌ها در startup.

قواعد:
- پیش‌فرض خاموش است (`ADAPTIVE_ROUTING_ENABLED=false`)؛ بدون تنظیم صریح هیچ
  رفتاری در gateway تغییر نمی‌کند.
- فقط taskهایی اعمال می‌شوند که **آمار ثبت‌شده** دارند؛ task بی‌سابقه به مسیر
  static خودش می‌ماند تا زنجیره‌ی خالی ساخته نشود.
- منطق امتیازدهی بازنویسی نمی‌شود؛ همان `AdaptiveRouter.build_routes` استفاده
  می‌شود و خروجی به `AIGateway.set_routes` می‌رود.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

DEFAULT_TASKS: tuple[str, ...] = ("classify_article", "extract_relations")


def parse_tasks(raw: str | None) -> list[str]:
    """CSV → لیست یکتا و مرتب؛ خالی → پیش‌فرض‌ها."""
    seen: list[str] = []
    for item in (raw or "").split(","):
        task = item.strip()
        if task and task not in seen:
            seen.append(task)
    return seen or list(DEFAULT_TASKS)


def build_effective_routes(db: Session, tasks: list[str]) -> dict[str, list[str]]:
    """زنجیره‌های پیشنهادی فقط برای taskهای دارای شاهد؛ بقیه حذف می‌شوند."""
    from domains.ai_routing.router import AdaptiveRouter

    routes = AdaptiveRouter(db).build_routes(tasks)
    return {
        task: list(route.providers)
        for task, route in routes.items()
        if route.providers  # بدون آمار → مسیر static دست‌نخورده می‌ماند
    }


def apply_adaptive_routes(db: Session, tasks: list[str]) -> dict[str, list[str]]:
    """زنجیره‌های مؤثر را روی gateway موجود اعمال می‌کند؛ خروجی برای لاگ."""
    from backend.ai.gateway import get_gateway
    from backend.ai.routing.router import Route

    effective = build_effective_routes(db, tasks)
    if not effective:
        return {}
    get_gateway().set_routes(
        {task: Route(role=task, providers=providers) for task, providers in effective.items()}
    )
    return effective


__all__ = ["DEFAULT_TASKS", "apply_adaptive_routes", "build_effective_routes", "parse_tasks"]
