"""Application configuration.

تنظیمات از متغیرهای محیطی (و در صورت وجود، فایل `.env`) خوانده می‌شود.
هیچ مقدار حساسی داخل کد hard-code نمی‌شود (Rule 7).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

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
    api_key: str | None = None
    access_token_expire_minutes: int = 60
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"
    rate_limit_per_minute: int = 600
    rate_limit_enabled: bool = True

    # --- Mock / Offline mode ---
    mock_mode: bool = True

    # --- Database ---
    database_url: str = (
        "postgresql+psycopg://gi_user:change-me-in-production@localhost:5432/globalintelligence"
    )
    # E2E FIND: burst ساعتی n8n pool پیش‌فرض (5+10) را تمام می‌کرد (QueuePool timeout → 500)
    db_pool_size: int = 10
    db_max_overflow: int = 20
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
    gemini_model: str = "gemini-3.5-flash"

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-3-5-haiku-latest"

    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openai/gpt-4o-mini"

    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-20b"

    cloudflare_api_token: str | None = None
    cloudflare_account_id: str | None = None

    # --- Settings panel encryption (Step 8) ---
    # کلید Fernet برای رمزنگاری اعتبارنامه‌ها در DB؛ بدون آن ذخیره‌ی کلید رد می‌شود.
    app_encryption_key: str | None = None
    # اجازه‌ی base_url خصوصی برای Provider سفارشی (پیش‌فرض بسته؛ ضد SSRF)
    allow_private_base_url: bool = False

    # --- Dashboard login (Step 8; UX: نام کاربری/رمز به‌جای تایپ کلید) ---
    # پیش‌فرض admin/admin برای لوکال؛ در production باید عوض شود (fail-fast).
    admin_username: str = "admin"
    admin_password: str = "admin"

    # --- Debate Engine (Step 3) ---
    debate_max_tokens_per_run: int = 60000
    debate_daily_budget_usd: float = 5.0
    debate_max_rounds: int = 2
    debate_call_gap_seconds: float = 0.0
    debate_model_bull: str | None = None
    debate_model_bear: str | None = None
    debate_model_macro: str | None = None
    debate_model_geo: str | None = None
    debate_model_critic: str | None = None
    debate_model_report: str | None = None

    # --- Data collection ---
    source_min_interval_seconds: int = 60
    user_agent: str = "GlobalIntelligenceBot/0.1 (+https://example.local; contact@example.local)"
    dedup_on_ingest: bool = False
    dedup_near_threshold: float = 0.7
    dedup_window: int = 1000

    # --- Frontend ---
    vite_api_base_url: str = "http://localhost:8000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    def validate_production(self) -> None:
        """در production، مقادیر پیش‌فرض ناامن باعث fail-fast می‌شوند (بند 69)."""
        if self.app_env != "production":
            return
        problems = []
        if self.secret_key in ("", "change-me-in-production"):
            problems.append("SECRET_KEY must be set")
        if not self.api_key:
            problems.append("API_KEY must be set")
        if self.mock_mode:
            problems.append("MOCK_MODE must be false in production")
        if self.debug:
            problems.append("DEBUG must be false in production")
        # AUDIT-REPAIR: رمز پیش‌فرض دیتابیس و CORS باز هم ناامن‌اند
        # (DATABASE_URL عمداً چک نمی‌شود: ممکن است رمز را جداگانه بگیرد)
        if self.postgres_password in ("", "change-me-in-production"):
            problems.append("POSTGRES_PASSWORD must be set")
        if "*" in self.cors_origins:
            problems.append("ALLOWED_ORIGINS must not contain '*' in production")
        if self.admin_password == "admin":
            problems.append("ADMIN_PASSWORD must be changed in production")
        if problems:
            raise ValueError("insecure production configuration: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    """یک نمونه‌ی singleton از تنظیمات برمی‌گرداند."""
    return Settings()
