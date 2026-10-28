"""Kev/Laya local decision providers — System One HTTP API.

Both projects serve the same wire protocol: ``POST /v1/systemone`` with a
``state`` plus typed ``questions`` (``noul`` / ``choice`` / ``score``).
They are local, zero-cost inference servers: this adapter only speaks HTTP
and never imports their Python packages or downloads weights.

Failure is explicit: connection/timeout/invalid output become ``AIError`` so
the screening service can abstain and let the existing pipeline continue.
"""
from __future__ import annotations

import json
import math
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.ai.providers.base import BaseProvider
from backend.ai.schemas.types import (
    AIError,
    AIErrorKind,
    AIRequest,
    AIResponse,
    AIUsage,
    ProviderHealth,
)
from backend.core.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def _normalise_url(url: str) -> str:
    """Validate a local endpoint URL without the cloud SSRF rule (loopback is expected)."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("local screening base_url must be http(s) with a host")
    if parsed.username or parsed.password:
        raise ValueError("local screening base_url must not contain userinfo")
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


def _probability(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def _validate_answers(answers: Any) -> dict[str, dict[str, Any]]:
    """Validate the System One answer envelope; raises ValueError on bad output."""
    if not isinstance(answers, dict) or not answers:
        raise ValueError("missing answers object")
    for question_id, answer in answers.items():
        if not isinstance(question_id, str) or not question_id:
            raise ValueError("question id must be a non-empty string")
        if not isinstance(answer, dict):
            raise ValueError(f"answer {question_id} is not an object")
        kind = answer.get("type")
        if kind == "noul":
            if not _probability(answer.get("noul")):
                raise ValueError(f"answer {question_id} has invalid noul probability")
        elif kind == "choice":
            if not isinstance(answer.get("choice"), str) or not answer["choice"]:
                raise ValueError(f"answer {question_id} has invalid choice")
            if not _probability(answer.get("confidence")):
                raise ValueError(f"answer {question_id} has invalid confidence")
        elif kind == "score":
            score = answer.get("score")
            if (not isinstance(score, (int, float)) or isinstance(score, bool)
                    or not math.isfinite(float(score))):
                raise ValueError(f"answer {question_id} has invalid score")
            if not _probability(answer.get("confidence")):
                raise ValueError(f"answer {question_id} has invalid confidence")
        else:
            raise ValueError(f"answer {question_id} has unknown type")
        probabilities = answer.get("probabilities")
        if probabilities is not None:
            if not isinstance(probabilities, dict) or not probabilities:
                raise ValueError(f"answer {question_id} has invalid probabilities")
            if any(not _probability(v) for v in probabilities.values()):
                raise ValueError(f"answer {question_id} has invalid probabilities")
    return answers


class LocalDecisionProvider(BaseProvider):
    """Base adapter for a Kev/Laya System One endpoint."""

    is_local = True
    name = "local_decision"
    default_model = ""
    _base_url_setting = ""
    _model_setting = ""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = get_settings()
        configured_url = base_url or str(getattr(settings, self._base_url_setting))
        self.base_url = _normalise_url(configured_url)
        self.default_model = (
            default_model or str(getattr(settings, self._model_setting) or "")
        )
        if not self.default_model:
            raise ValueError(f"{self.name} has no default model")
        self.api_key = api_key or None
        self._timeout = float(settings.local_screening_timeout_seconds)
        self._transport = transport

    def configured(self) -> bool:
        return bool(self.base_url and self.default_model)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _endpoint(self) -> str:
        return f"{self.base_url}/v1/systemone"

    async def generate(self, request: AIRequest) -> AIResponse:
        if not self.configured():
            raise AIError(
                f"provider '{self.name}' is not configured",
                kind=AIErrorKind.auth, provider=self.name, retryable=False,
            )
        state = next(
            (m.content for m in reversed(request.messages) if m.role == "user"), ""
        )
        questions = request.metadata.get("questions")
        if not state.strip():
            raise AIError("local screening state is empty",
                          kind=AIErrorKind.invalid_output,
                          provider=self.name, retryable=False)
        if not isinstance(questions, dict) or not questions:
            raise AIError("local screening questions are missing",
                          kind=AIErrorKind.invalid_output,
                          provider=self.name, retryable=False)

        model = str(request.metadata.get("model") or self.default_model)
        payload = {"state": state, "model": model, "questions": questions}
        timeout = float(request.metadata.get("timeout") or self._timeout)
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                follow_redirects=False,
                transport=self._transport,
                trust_env=False,
            ) as client:
                response = await client.post(
                    self._endpoint(), json=payload, headers=self._headers(),
                )
        except httpx.TimeoutException as exc:
            raise AIError(str(exc), kind=AIErrorKind.timeout,
                          provider=self.name, retryable=False) from exc
        except httpx.HTTPError as exc:
            raise AIError(str(exc), kind=AIErrorKind.connection,
                          provider=self.name, retryable=False) from exc

        if len(response.content) > MAX_RESPONSE_BYTES:
            raise AIError("response too large", kind=AIErrorKind.invalid_output,
                          provider=self.name, retryable=False)
        status = response.status_code
        if status in (401, 403):
            raise AIError("auth failed", kind=AIErrorKind.auth,
                          provider=self.name, retryable=False)
        if status == 429:
            raise AIError("rate limited", kind=AIErrorKind.rate_limit,
                          provider=self.name, retryable=False)
        if status >= 500:
            raise AIError(f"provider error {status}", kind=AIErrorKind.provider_error,
                          provider=self.name, retryable=False)
        if status >= 400:
            raise AIError(f"bad request {status}", kind=AIErrorKind.bad_request,
                          provider=self.name, retryable=False)

        try:
            data = response.json()
            answers = _validate_answers(data.get("answers"))
        except Exception as exc:  # noqa: BLE001
            raise AIError(f"invalid provider output: {exc}",
                          kind=AIErrorKind.invalid_output,
                          provider=self.name, retryable=False) from exc

        usage = data.get("usage") or {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        latency = data.get("latency_ms")
        if not isinstance(latency, (int, float)) or isinstance(latency, bool):
            latency = (time.perf_counter() - started) * 1000
        resolved_model = str(data.get("model") or model)
        text = json.dumps({"answers": answers}, ensure_ascii=False)
        return AIResponse(
            text=text,
            provider=self.name,
            model=resolved_model,
            usage=AIUsage(
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
                total_tokens=(
                    int(input_tokens) + int(output_tokens)
                    if isinstance(input_tokens, int) and isinstance(output_tokens, int)
                    else None
                ),
            ),
            cost_estimate=0.0,
            latency_ms=float(latency),
            structured={"answers": answers},
            raw=data,
            model_version=resolved_model,
            prompt_version=request.metadata.get("prompt_version", "v0"),
        )

    async def health(self) -> ProviderHealth:
        if not self.configured():
            return ProviderHealth(provider=self.name, healthy=False,
                                  detail="not configured")
        # No request is sent: health checks must stay cheap and offline-safe.
        return ProviderHealth(provider=self.name, healthy=True,
                              detail="local endpoint configured (not probed)")


class KevProvider(LocalDecisionProvider):
    name = "kev"
    _base_url_setting = "local_screening_kev_base_url"
    _model_setting = "local_screening_kev_model"


class LayaProvider(LocalDecisionProvider):
    name = "laya"
    _base_url_setting = "local_screening_laya_base_url"
    _model_setting = "local_screening_laya_model"
