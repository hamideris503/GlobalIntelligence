"""Root & health endpoints.

- `/`              : اطلاعات پایه‌ی سرویس
- `/health`        : liveness (سرویس بالا است)
- `/health/db`     : readiness دیتابیس (عمومی، فقط وضعیت)
- `/health/db/details`: جزئیات نسخه/مهاجرت/خطا (نیازمند احراز هویت)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.auth.deps import CurrentUser, require_user
from backend.database.session import check_database

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/health/db")
def health_db() -> dict[str, str]:
    """Readiness probe برای دیتابیس.

    پاسخ عمومی فقط وضعیت است؛ نسخهٔ سرور، revision مهاجرت و متن خطا
    افشای اطلاعات داخلی‌اند و در `/health/db/details` پشت auth می‌مانند.
    """
    result = check_database()
    return {"status": "ok" if result["ok"] else "degraded"}


@router.get("/health/db/details")
def health_db_details(_: CurrentUser = Depends(require_user)) -> dict[str, object]:
    """همان readiness، با جزئیات تشخیصی برای اپراتور."""
    result = check_database()
    return {"status": "ok" if result["ok"] else "degraded", "database": result}
