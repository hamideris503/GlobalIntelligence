"""Promote every existing account to admin (single-owner deployment policy)."""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "a9f1c2d3e4b5"
down_revision: str | None = "f0auth_users_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # سیاست جدید: همهٔ حساب‌ها (نه فقط حساب seed) دسترسی کامل مدیریتی دارند.
    # حساب‌های ثبت‌شده پیش از این تغییر با نقش viewer/analyst باقی می‌ماندند.
    op.execute(
        sa.text("UPDATE users SET role = 'admin' WHERE role <> 'admin' OR role IS NULL")
    )


def downgrade() -> None:
    # نقش قبلی هر کاربر ذخیره نشده و قابل بازگردانی نیست؛ این گام عمداً بی‌اثر است.
    pass
