"""Application configuration.

تنظیمات از متغیرهای محیطی (و در صورت وجود، فایل `.env`) خوانده می‌شود.
هیچ مقدار حساسی داخل کد hard-code نمی‌شود (Rule 7).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """تنظیمات مرکزی برنامه."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "GlobalIntelligence"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    log_level: str = "INFO"
    tz: str = "UTC"

    # --- Security ---
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- Mock / Offline mode ---
    mock_mode: bool = True

    # --- Database ---
    database_url: str = (
        "postgresql+psycopg://gi_user:change-me-in-production@localhost:5432/globalintelligence"
    )
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "globalintelligence"
    postgres_user: str = "gi_user"
    postgres_password: str = "change-me-in-production"

    # --- AI Gateway ---
    ai_default_provider: str = "mock"
    ai_request_timeout_seconds: int = 60
    ai_max_retries: int = 2
    ai_enable_cost_tracking: bool = True

    # Provider credentials (همه Optional — بدون آن Provider غیرفعال می‌شود)
    gemini_api_key: str | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com"
    gemini_model: str = "gemini-1.5-flash"

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-3-5-haiku-latest"

    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openai/gpt-4o-mini"

    # --- Frontend ---
    vite_api_base_url: str = "http://localhost:8000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """یک نمونه‌ی singleton از تنظیمات برمی‌گرداند."""
    return Settings()
