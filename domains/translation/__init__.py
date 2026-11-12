"""Offline translation (Stage 101) — فقط برای نمایش.

ترجمه lazy و فقط برای نمایش؛ تحلیل و طبقه‌بندی روی متن اصلی.
cache بر پایهٔ hash متن اصلی + زبان مبدأ/مقصد + نسخهٔ مدل.
خطای ترجمه، دریافت خبر و تحلیل اصلی را متوقف نکند.
"""

from domains.translation.service import TranslationService, TranslationResult

__all__ = ["TranslationService", "TranslationResult"]