"""Settings API schemas (Step 8) — بدون هیچ مقدار محرمانه در پاسخ."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    kind: str = Field(..., min_length=1, max_length=32)
    base_url: str | None = None
    api_key: str | None = None  # write-only
    extra: dict[str, str] | None = None  # write-only (مثل account_id)
    enabled: bool = True
    # مدل پیش‌فرض اختیاری (همان فرم افزودن؛ قیمت بعداً در تب مدل‌ها)
    default_model: str | None = Field(default=None, max_length=128)


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    base_url: str | None = None
    api_key: str | None = None  # write-only (rotate)
    extra: dict[str, str] | None = None  # write-only
    enabled: bool | None = None


class ProviderRead(BaseModel):
    id: str
    name: str
    kind: str
    base_url: str | None
    key_set: bool
    key_hint: str
    key_source: str = "db"  # db | env (کلید .env فقط‌خواندنی است)
    enabled: bool
    last_test_status: str | None
    last_tested_at: str | None


class ProviderTestRequest(BaseModel):
    model: str | None = None


class ProviderTestResponse(BaseModel):
    ok: bool
    provider: str
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: float | None = None
    error: str | None = None


class KeyRotateRequest(BaseModel):
    api_key: str = Field(..., min_length=8, max_length=500)


class ModelCreate(BaseModel):
    provider_id: str
    model_name: str = Field(..., min_length=1, max_length=128)
    price_in_per_mtok: float | None = Field(default=None, ge=0)
    price_out_per_mtok: float | None = Field(default=None, ge=0)
    enabled: bool = True


class ModelUpdate(BaseModel):
    model_name: str | None = Field(default=None, min_length=1, max_length=128)
    price_in_per_mtok: float | None = Field(default=None, ge=0)
    price_out_per_mtok: float | None = Field(default=None, ge=0)
    enabled: bool | None = None


class ModelRead(BaseModel):
    id: str
    provider_id: str
    provider_name: str
    model_name: str
    price_in_per_mtok: float | None
    price_out_per_mtok: float | None
    enabled: bool


class AssignmentItem(BaseModel):
    agent: str
    provider_id: str | None = None
    model_id: str | None = None
    enabled: bool = True


class AssignmentRead(BaseModel):
    agent: str
    provider_id: str | None
    provider_name: str | None
    model_id: str | None
    model_name: str | None
    enabled: bool


class DiversityRead(BaseModel):
    distinct_models: int
    distinct_providers: int
    warning: str | None = None


class AppSettingsUpdate(BaseModel):
    settings: dict[str, str]


class ImportEnvResponse(BaseModel):
    moved: list[str] = []
    skipped: list[str] = []
    needs_encryption_key: bool = False


class VoidRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)
