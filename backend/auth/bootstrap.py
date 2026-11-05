"""seed کاربر admin اولیه از متغیرهای محیطی (بدون مقدار پیش‌فرض در کد)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.passwords import hash_password
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.database.models.user import User

logger = get_logger(__name__)


def seed_admin_user(db: Session) -> None:
    """اگر ADMIN_USERNAME/ADMIN_PASSWORD تنظیم شده و کاربر وجود ندارد، می‌سازد.

    رمز هرگز لاگ نمی‌شود و کاربر موجود بازنویسی نمی‌شود.
    """
    settings = get_settings()
    username = (settings.admin_username or "").strip()
    password = settings.admin_password or ""
    if not username or not password:
        logger.warning(
            "initial admin not seeded: ADMIN_USERNAME/ADMIN_PASSWORD are not set"
        )
        return
    existing = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if existing is not None:
        logger.info("initial admin already exists | username=%s", username)
        return
    db.add(
        User(
            username=username,
            password_hash=hash_password(password),
            role="admin",
            active=True,
        )
    )
    db.commit()
    logger.info("initial admin seeded | username=%s", username)
