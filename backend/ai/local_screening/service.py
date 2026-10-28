"""Advisory local screening via Kev/Laya (default off, never a second gateway).

The deterministic pipeline still owns every decision. This service only asks
one typed ``noul`` question per article and returns an advisory result the
classifier records in its metadata. Low confidence, conflicts, missing models,
timeouts and invalid output all abstain; cloud classification then proceeds
unchanged.

Both providers are reached through the existing ``AIGateway`` (forced by
provider name), so routing, logging, provider health and the shared provider
registry stay in one place.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field, replace
from threading import Lock
from typing import Any, Literal

from backend.ai.gateway import get_gateway
from backend.ai.schemas.types import AIError, AIRequest, Message
from backend.core.config import Settings, get_settings
from backend.core.logging import get_logger
from backend.core.mock_mode import effective_mock_mode

logger = get_logger(__name__)

QUESTION_ID = "relevant"
LEGACY_SCOPE_RULE_VERSION = "relevance_scope_v1"
SCOPE_RULE_VERSION = "relevance_scope_v2"
SCOPE_DOMAINS: tuple[str, ...] = (
    "macroeconomics",
    "monetary or fiscal policy",
    "markets or finance",
    "energy",
    "geopolitics",
    "trade",
    "technology",
    "health",
    "climate",
)

# Frozen v1 question. Keep byte-identical: the stage53 dataset embeds this text
# and the offline stage55 evaluator refuses to run without it.
SCREENING_QUESTIONS: dict[str, dict[str, Any]] = {
    QUESTION_ID: {
        "type": "noul",
        "instructions": (
            "Is this article relevant to the project's analytical scope: "
            "macroeconomics, monetary or fiscal policy, markets, energy, "
            "geopolitics, trade, technology, health, or climate?"
        ),
    }
}

# v2: relevance is decided by the article's main subject, not by mentions.
SCREENING_QUESTIONS_V2: dict[str, dict[str, Any]] = {
    QUESTION_ID: {
        "type": "noul",
        "instructions": (
            "Judge the article's main subject, not its passing mentions. Is the "
            "article mainly about one of the project's analytical domains: "
            "macroeconomics, monetary or fiscal policy, markets or finance, energy, "
            "geopolitics, trade, technology, health, or climate? A secondary section "
            "or a brief reference to a domain does not make the article relevant. "
            "Article format (news, interview, obituary, cultural piece) does not "
            "decide the answer."
        ),
    }
}

CURRENT_QUESTION_SET = SCREENING_QUESTIONS_V2
QUESTION_SETS: dict[str, dict[str, dict[str, Any]]] = {
    LEGACY_SCOPE_RULE_VERSION: SCREENING_QUESTIONS,
    SCOPE_RULE_VERSION: SCREENING_QUESTIONS_V2,
}


def question_set_version(questions: Any) -> str | None:
    """Return the registered contract version of a question set, else None."""
    for version, known in QUESTION_SETS.items():
        if questions == known:
            return version
    return None

ScreeningStatus = Literal["decided", "abstained", "unavailable", "skipped"]


@dataclass(frozen=True)
class ScreeningAttempt:
    provider: str
    model: str | None
    status: str  # ok | low_confidence | invalid | unavailable | error
    decision: bool | None = None
    confidence: float | None = None
    latency_ms: float = 0.0
    reason: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "decision": self.decision,
            "confidence": self.confidence,
            "latency_ms": round(self.latency_ms, 1),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ScreeningResult:
    status: ScreeningStatus
    decision: bool | None = None
    confidence: float | None = None
    provider: str | None = None
    model: str | None = None
    reason: str | None = None
    latency_ms: float = 0.0
    scope_rule_version: str = SCOPE_RULE_VERSION
    input_chars: int | None = None
    truncated: bool = False
    attempts: tuple[ScreeningAttempt, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "decision": self.decision,
            "confidence": self.confidence,
            "provider": self.provider,
            "model": self.model,
            "reason": self.reason,
            "latency_ms": round(self.latency_ms, 1),
            "scope_rule_version": self.scope_rule_version,
            "input_chars": self.input_chars,
            "truncated": self.truncated,
            "attempts": [a.as_dict() for a in self.attempts],
        }

    @classmethod
    def skipped(cls, reason: str) -> ScreeningResult:
        return cls(status="skipped", reason=reason)


@dataclass
class ProviderScreeningStats:
    calls: int = 0
    success: int = 0
    errors: int = 0
    timeouts: int = 0
    connection_errors: int = 0
    invalid: int = 0
    unavailable: int = 0
    low_confidence: int = 0
    decided: int = 0
    abstained: int = 0
    total_latency_ms: float = 0.0

    def as_dict(self) -> dict[str, float | int | None]:
        return {
            "calls": self.calls,
            "success": self.success,
            "errors": self.errors,
            "timeouts": self.timeouts,
            "connection_errors": self.connection_errors,
            "invalid": self.invalid,
            "unavailable": self.unavailable,
            "low_confidence": self.low_confidence,
            "decided": self.decided,
            "abstained": self.abstained,
            "total_latency_ms": round(self.total_latency_ms, 1),
            "avg_latency_ms": (
                round(self.total_latency_ms / self.calls, 1)
                if self.calls else None
            ),
        }


@dataclass
class ScreeningStats:
    """Thread-safe process-wide counters for advisory screening.

    ``screens`` counts actual screening runs; ``calls`` counts individual
    provider requests. A skipped run (disabled/mock/invalid config) never
    becomes a model call. Nothing here stores text or prompt content.
    """

    screens: int = 0
    skipped: int = 0
    calls: int = 0
    success: int = 0
    errors: int = 0
    timeouts: int = 0
    connection_errors: int = 0
    invalid: int = 0
    unavailable: int = 0
    decided: int = 0
    abstained: int = 0
    total_latency_ms: float = 0.0
    providers: dict[str, ProviderScreeningStats] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, repr=False, compare=False)

    def reset(self) -> None:
        with self._lock:
            self.screens = 0
            self.skipped = 0
            self.calls = 0
            self.success = 0
            self.errors = 0
            self.timeouts = 0
            self.connection_errors = 0
            self.invalid = 0
            self.unavailable = 0
            self.decided = 0
            self.abstained = 0
            self.total_latency_ms = 0.0
            self.providers.clear()

    def record_screen(self) -> None:
        with self._lock:
            self.screens += 1

    def record_skip(self) -> None:
        with self._lock:
            self.skipped += 1

    def record_attempt(
        self, provider: str, status: str, latency_ms: float, reason: str | None = None,
    ) -> None:
        with self._lock:
            self.calls += 1
            self.total_latency_ms += latency_ms
            item = self.providers.setdefault(provider, ProviderScreeningStats())
            item.calls += 1
            item.total_latency_ms += latency_ms
            if status in ("ok", "low_confidence"):
                self.success += 1
                item.success += 1
                if status == "low_confidence":
                    item.low_confidence += 1
                return
            self.errors += 1
            item.errors += 1
            if reason == "timeout":
                self.timeouts += 1
                item.timeouts += 1
            elif reason == "connection":
                self.connection_errors += 1
                item.connection_errors += 1
            elif status == "invalid" or reason == "invalid_output":
                self.invalid += 1
                item.invalid += 1
            else:
                self.unavailable += 1
                item.unavailable += 1

    def record_result(self, status: str, provider: str | None) -> None:
        with self._lock:
            if status == "decided":
                self.decided += 1
                if provider:
                    self.providers.setdefault(
                        provider, ProviderScreeningStats()
                    ).decided += 1
            elif status in ("abstained", "unavailable"):
                self.abstained += 1
                if provider:
                    self.providers.setdefault(
                        provider, ProviderScreeningStats()
                    ).abstained += 1

    def as_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "screens": self.screens,
                "skipped": self.skipped,
                "calls": self.calls,
                "success": self.success,
                "errors": self.errors,
                "timeouts": self.timeouts,
                "connection_errors": self.connection_errors,
                "invalid": self.invalid,
                "unavailable": self.unavailable,
                "decided": self.decided,
                "abstained": self.abstained,
                "total_latency_ms": round(self.total_latency_ms, 1),
                "avg_latency_ms": (
                    round(self.total_latency_ms / self.calls, 1)
                    if self.calls else None
                ),
                "providers": {
                    name: item.as_dict() for name, item in self.providers.items()
                },
            }


_DEFAULT_STATS = ScreeningStats()


def get_screening_stats() -> ScreeningStats:
    """Return the process-wide counters exposed by /api/ops/metrics."""
    return _DEFAULT_STATS


def _noul_probability(response) -> float:
    """Extract the calibrated P(yes) for the single screening question."""
    structured = response.structured or {}
    answers = structured.get("answers")
    if not isinstance(answers, dict):
        raise ValueError("missing answers")
    answer = answers.get(QUESTION_ID)
    if not isinstance(answer, dict) or answer.get("type") != "noul":
        raise ValueError("missing noul answer")
    value = answer.get("noul")
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0):
        raise ValueError("invalid noul probability")
    return float(value)


class LocalScreener:
    """DEPRECATED (Stage89) — kept only for the offline evaluation/lab suite.

    The production classifier no longer constructs this class. Screening in
    production goes through ``orchestrator.screen_with_db``, which owns the
    per-model flags, the runtime supervisor and the AI Gateway fallback. The
    legacy master switch (``local_screening_enabled``) is ignored.

    Its endpoint defaults now point at the supervised ports (8123/8124), not
    the retired 8009/8011 servers, so no code path can silently start or call
    a second local server.
    """

    def __init__(
        self,
        gateway=None,  # noqa: ANN001 - testable seam
        *,
        settings: Settings | None = None,
        mock_mode: bool | None = None,
        stats: ScreeningStats | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._gateway = gateway or get_gateway()
        self._mock_mode = effective_mock_mode() if mock_mode is None else mock_mode
        self._stats = get_screening_stats() if stats is None else stats

    @property
    def stats(self) -> ScreeningStats:
        return self._stats

    def _providers(self) -> list[str]:
        raw = (self._settings.local_screening_providers or "").split(",")
        seen: set[str] = set()
        out: list[str] = []
        for name in (p.strip().lower() for p in raw):
            if name and name not in seen:
                seen.add(name)
                out.append(name)
        return out

    def _model(self, provider: str) -> str:
        if provider == "kev":
            return self._settings.local_screening_kev_model
        if provider == "laya":
            return self._settings.local_screening_laya_model
        return ""

    def _skip(self, reason: str) -> ScreeningResult:
        self._stats.record_skip()
        return ScreeningResult.skipped(reason)

    async def screen(
        self, text: str, *, deterministic: bool | None = None,
    ) -> ScreeningResult:
        """Return an advisory decision; never raise into the caller's pipeline."""
        if not self._settings.local_screening_enabled:
            return self._skip("disabled")
        if self._mock_mode:
            return self._skip("mock_mode")
        if not text.strip():
            return self._skip("empty_text")

        threshold = float(self._settings.local_screening_confidence_threshold)
        timeout = float(self._settings.local_screening_timeout_seconds)
        max_chars = int(self._settings.local_screening_max_chars)
        if not 0.0 <= threshold <= 1.0:
            return self._skip("invalid_threshold")
        if timeout <= 0:
            return self._skip("invalid_timeout")
        if max_chars <= 0:
            return self._skip("invalid_max_chars")
        state = text[:max_chars]
        truncated = len(text) > max_chars
        self._stats.record_screen()
        attempts: list[ScreeningAttempt] = []
        candidates: list[ScreeningAttempt] = []

        for provider in self._providers():
            model = self._model(provider)
            if provider not in ("kev", "laya") or not model:
                attempts.append(ScreeningAttempt(
                    provider=provider, model=model or None, status="unavailable",
                    reason="unknown_provider",
                ))
                continue
            started = time.perf_counter()
            try:
                response = await self._gateway.generate(AIRequest(
                    messages=[Message.user(state)],
                    role="local_screening",
                    task="local_screening",
                    temperature=0.0,
                    metadata={
                        "force_provider": provider,
                        "questions": CURRENT_QUESTION_SET,
                        "scope_rule_version": SCOPE_RULE_VERSION,
                        "timeout": timeout,
                    },
                ))
                probability = _noul_probability(response)
            except AIError as exc:
                latency = (time.perf_counter() - started) * 1000
                status = (
                    "unavailable"
                    if exc.kind.value in (
                        "connection", "timeout", "auth", "provider_error",
                        "rate_limit", "provider_not_allowed", "model_not_allowed",
                    )
                    else "invalid"
                )
                attempts.append(ScreeningAttempt(
                    provider=provider, model=model or None, status=status,
                    latency_ms=latency, reason=exc.kind.value,
                ))
                self._stats.record_attempt(
                    provider, status, latency, reason=exc.kind.value,
                )
                continue
            except Exception as exc:  # noqa: BLE001 - screening must never break ingestion
                latency = (time.perf_counter() - started) * 1000
                attempts.append(ScreeningAttempt(
                    provider=provider, model=model or None, status="error",
                    latency_ms=latency, reason=type(exc).__name__,
                ))
                self._stats.record_attempt(
                    provider, "error", latency, reason=type(exc).__name__,
                )
                logger.warning("local screening failed | provider=%s err=%s",
                               provider, type(exc).__name__)
                continue

            latency = (time.perf_counter() - started) * 1000
            confidence = max(probability, 1.0 - probability)
            decision = probability >= 0.5
            attempt = ScreeningAttempt(
                provider=provider,
                model=response.model or model,
                status="ok" if confidence >= threshold else "low_confidence",
                decision=decision,
                confidence=confidence,
                latency_ms=latency,
                reason=None if confidence >= threshold else "below_threshold",
            )
            attempts.append(attempt)
            self._stats.record_attempt(
                provider, attempt.status, latency, reason=attempt.reason,
            )
            if confidence >= threshold:
                candidates.append(attempt)

        result = replace(
            self._resolve(attempts, candidates, deterministic),
            scope_rule_version=SCOPE_RULE_VERSION,
            input_chars=len(text),
            truncated=truncated,
        )
        self._stats.record_result(result.status, result.provider)
        logger.info(
            "local screening | status=%s provider=%s decision=%s confidence=%s "
            "latency_ms=%.1f",
            result.status, result.provider, result.decision, result.confidence,
            result.latency_ms,
        )
        return result

    def _resolve(
        self,
        attempts: list[ScreeningAttempt],
        candidates: list[ScreeningAttempt],
        deterministic: bool | None,
    ) -> ScreeningResult:
        latency = sum(a.latency_ms for a in attempts)
        if candidates:
            decisions = {a.decision for a in candidates}
            if len(decisions) > 1:
                return ScreeningResult(
                    status="abstained", reason="conflict", latency_ms=latency,
                    attempts=tuple(attempts),
                )
            chosen = max(candidates, key=lambda a: a.confidence or 0.0)
            if deterministic is not None and chosen.decision != deterministic:
                return ScreeningResult(
                    status="abstained", provider=chosen.provider,
                    model=chosen.model, decision=chosen.decision,
                    confidence=chosen.confidence, reason="conflict_with_rules",
                    latency_ms=latency, attempts=tuple(attempts),
                )
            return ScreeningResult(
                status="decided", provider=chosen.provider, model=chosen.model,
                decision=chosen.decision, confidence=chosen.confidence,
                latency_ms=latency, attempts=tuple(attempts),
            )
        if any(a.status in ("ok", "low_confidence") for a in attempts):
            return ScreeningResult(
                status="abstained", reason="low_confidence",
                latency_ms=latency, attempts=tuple(attempts),
            )
        if attempts:
            return ScreeningResult(
                status="unavailable", reason="no_usable_provider",
                latency_ms=latency, attempts=tuple(attempts),
            )
        return ScreeningResult(status="unavailable", reason="no_provider_configured")
