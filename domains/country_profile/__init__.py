"""Country Profile — پروفایل کشور قابل تنظیم (Stage 99).

«حالت ایران» به مدل پروفایل عمومی تبدیل شده است؛ رفتار فعلی = پروفایل پایهٔ IR.
بدون تغییر رفتار برای ایران (تست مقایسه‌ای).
"""

from domains.country_profile.profile import CountryProfile
from domains.country_profile.registry import get_profile, list_profiles, register_profile

__all__ = ["CountryProfile", "get_profile", "list_profiles", "register_profile"]