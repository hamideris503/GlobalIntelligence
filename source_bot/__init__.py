"""Source bot — ربات مرکزی استخراج، dedup و اولویت‌بندی.

قرارداد ورودی/خروجی همان RawItem پروژه است (domains/news/fetchers.py)؛
قرارداد موازی ساخته نمی‌شود. ذخیره‌سازی فقط از طریق
NewsIngestionPipeline موجود انجام می‌شود.
"""
from source_bot.config import BotSettings, get_bot_settings

__all__ = ["BotSettings", "get_bot_settings"]
