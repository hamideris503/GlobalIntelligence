"""Evidence model — جدا شده در فایل مستقل برای import صحیح.

در `claim.py` تعریف شده؛ این ماژول فقط re-export می‌کند.
"""
from backend.database.models.claim import Evidence

__all__ = ["Evidence"]
