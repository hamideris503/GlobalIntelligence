"""Root & health endpoints.

- `/`         : اطلاعات پایه‌ی سرویس
- `/health`   : liveness (سرویس بالا است)
- `/health/db`: readiness دیتابیس
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.core.config import get_settings
from backend.database.session import check_database

router = APIRouter(tags=["system"])


@router.get("/")
def root() -> dict[str, str]:
    # AUDIT-REPAIR: env فاش نمی‌شود و لینک docs در production حذف است
    settings = get_settings()
    info: dict[str, str] = {"name": settings.app_name, "status": "ok"}
    if settings.app_env != "production":
        info["docs"] = "/docs"
    return info


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/health/db")
def health_db() -> dict[str, object]:
    """Readiness probe برای دیتابیس."""
    result = check_database()
    return {
        "status": "ok" if result["ok"] else "degraded",
        "database": result,
    }
