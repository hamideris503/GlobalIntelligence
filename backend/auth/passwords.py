"""هش و بررسی رمز عبور با Argon2id.

پارامترهای پیش‌فرض argon2-cffi (Argon2id, 64MB, 3 passes) برای رمز انسانی کافی
و قابل ارتقا هستند؛ رشته‌ی hash خودش الگوریتم/پارامترها را حمل می‌کند.
"""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

_hasher = PasswordHasher()

# هش ساختگی برای یکسان‌سازی زمان پاسخ وقتی نام کاربری وجود ندارد
# (جلوگیری از user enumeration بر اساس اختلاف زمان).
_DUMMY_HASH = _hasher.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerificationError:
        return False


def dummy_verify(password: str) -> None:
    """همان هزینه‌ی بررسی را پرداخت می‌کند بدون اینکه رمزی تأیید شود."""
    try:
        _hasher.verify(_DUMMY_HASH, password)
    except VerificationError:
        pass
