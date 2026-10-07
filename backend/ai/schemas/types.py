"""انواع مشترک AI Gateway.

هیچ نام Providerی در این schemas hard-code نمی‌شود (بند 11).
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["system", "user", "assistant"]


class AIErrorKind(str, enum.Enum):
    """دسته‌بندی خطاها برای تصمیم‌گیری gateway (retry/fallback)."""

    timeout = "timeout"
    rate_limit = "rate_limit"
    auth = "auth"
    connection = "connection"
    bad_request = "bad_request"
    provider_error = "provider_error"
    invalid_output = "invalid_output"
    unknown = "unknown"


class AIError(Exception):
    """خطای یکپارچه‌ی AI Gateway."""

    def __init__(self, message: str, *, kind: AIErrorKind = AIErrorKind.unknown,
                 provider: str | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.kind = kind
        self.provider = provider
        self.retryable = retryable


@dataclass
class Message:
    role: Role
    content: str

    @staticmethod
    def system(content: str) -> "Message":
        return Message(role="system", content=content)

    @staticmethod
    def user(content: str) -> "Message":
        return Message(role="user", content=content)

    @staticmethod
    def assistant(content: str) -> "Message":
        return Message(role="assistant", content=content)


@dataclass
class AIRequest:
    """درخواست به Gateway — مستقل از Provider."""

    messages: list[Message]
    task: str | None = None            # برای routing (extraction/analysis/...)
    role: str | None = None            # نقش منطقی (fast_extraction/critic/...)
    temperature: float = 0.2
    max_tokens: int | None = None
    json_schema: dict[str, Any] | None = None  # structured output
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AIUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class AIResponse:
    """پاسخ یکسان از همه‌ی Providerها."""

    text: str
    provider: str
    model: str
    usage: AIUsage = field(default_factory=AIUsage)
    cost_estimate: float | None = None
    latency_ms: float | None = None
    structured: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None
    model_version: str | None = None
    prompt_version: str | None = None


@dataclass
class ProviderHealth:
    provider: str
    healthy: bool
    detail: str = ""
