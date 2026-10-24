"""Focused, offline tests for Kev/Laya local screening (Stage 45)."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from backend.ai import free_policy
from backend.ai.evaluation.local_screening import (
    MIN_LABELED_SAMPLES,
    evaluate_noul,
    score_noul,
    validate_records,
)
from backend.ai.evaluation.local_screening import main as evaluation_main
from backend.ai.gateway.gateway import AIGateway
from backend.ai.local_screening import (
    LEGACY_SCOPE_RULE_VERSION,
    QUESTION_ID,
    SCOPE_DOMAINS,
    SCOPE_RULE_VERSION,
    SCREENING_QUESTIONS,
    SCREENING_QUESTIONS_V2,
    LocalScreener,
    ScreeningStats,
    question_set_version,
)
from backend.ai.providers.base import BaseProvider
from backend.ai.providers.local_decision import KevProvider
from backend.ai.providers.registry import build_provider
from backend.ai.schemas.types import (
    AIError,
    AIErrorKind,
    AIRequest,
    AIResponse,
    Message,
)
from backend.core.config import Settings


def _provider(handler, **kwargs) -> KevProvider:
    return KevProvider(
        base_url="http://127.0.0.1:8009",
        default_model="kev-latest",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def _request() -> AIRequest:
    return AIRequest(
        messages=[Message.user("A central bank raised rates today.")],
        task="local_screening",
        metadata={"questions": SCREENING_QUESTIONS},
    )


def _answer(probability: float = 0.9) -> dict:
    return {
        "model": "kev-latest",
        "answers": {
            QUESTION_ID: {"type": "noul", "noul": probability},
        },
        "usage": {"input_tokens": 10, "output_tokens": 2},
        "latency_ms": 12,
    }


# --- provider contract ---


def test_provider_returns_validated_structured_answer() -> None:
    response = asyncio.run(
        _provider(lambda request: httpx.Response(200, json=_answer(0.91))).generate(
            _request()
        )
    )
    assert response.provider == "kev"
    assert response.structured == {
        "answers": {QUESTION_ID: {"type": "noul", "noul": 0.91}}
    }
    assert response.usage.total_tokens == 12
    assert response.latency_ms == 12


def test_provider_accepts_choice_and_score_answers() -> None:
    payload = {
        "answers": {
            "topic": {
                "type": "choice", "choice": "markets", "confidence": 0.88,
                "probabilities": {"markets": 0.88, "energy": 0.12},
            },
            "impact": {"type": "score", "score": 2, "confidence": 0.7},
        }
    }
    response = asyncio.run(
        _provider(lambda request: httpx.Response(200, json=payload)).generate(_request())
    )
    assert set(response.structured["answers"]) == {"topic", "impact"}


def test_provider_rejects_invalid_probability() -> None:
    provider = _provider(lambda request: httpx.Response(200, json=_answer(1.2)))
    with pytest.raises(AIError) as exc:
        asyncio.run(provider.generate(_request()))
    assert exc.value.kind == AIErrorKind.invalid_output


def test_provider_maps_http_errors() -> None:
    provider = _provider(lambda request: httpx.Response(422, json={"detail": "bad"}))
    with pytest.raises(AIError) as exc:
        asyncio.run(provider.generate(_request()))
    assert exc.value.kind == AIErrorKind.bad_request


def test_provider_maps_timeout_and_connection() -> None:
    def timeout(request):
        raise httpx.TimeoutException("slow")

    def down(request):
        raise httpx.ConnectError("down")

    with pytest.raises(AIError) as exc:
        asyncio.run(_provider(timeout).generate(_request()))
    assert exc.value.kind == AIErrorKind.timeout
    with pytest.raises(AIError) as exc:
        asyncio.run(_provider(down).generate(_request()))
    assert exc.value.kind == AIErrorKind.connection


def test_provider_rejects_malformed_json() -> None:
    provider = _provider(
        lambda request: httpx.Response(200, content=b"not-json",
                                       headers={"content-type": "application/json"})
    )
    with pytest.raises(AIError) as exc:
        asyncio.run(provider.generate(_request()))
    assert exc.value.kind == AIErrorKind.invalid_output


# --- policy ---


def test_local_providers_are_outside_the_cloud_allowlist() -> None:
    free_policy.check_provider("kev", mock_mode=False)
    free_policy.check_model("kev", "kev-latest", mock_mode=False)
    free_policy.check_provider("laya", mock_mode=False)
    free_policy.check_model("laya", "jev-1", mock_mode=False)
    assert build_provider("kev").is_local
    assert build_provider("laya").is_local


def test_gateway_dispatches_forced_local_provider() -> None:
    """The existing gateway chain, policy and provider registry handle local models."""
    class _Ok(BaseProvider):
        name = "kev"
        default_model = "kev-latest"
        is_local = True

        async def generate(self, request: AIRequest) -> AIResponse:
            return AIResponse(text="ok", provider=self.name, model=self.default_model)

    gateway = AIGateway()
    gateway._settings.mock_mode = False
    gateway._settings.ai_default_provider = "kev"
    gateway._providers["kev"] = _Ok()
    response = asyncio.run(gateway.generate(AIRequest(
        messages=[Message.user("text")],
        metadata={"force_provider": "kev"},
    )))
    assert response.provider == "kev"


# --- service decision flow ---


class _FakeGateway:
    def __init__(self, results: dict[str, float | Exception]) -> None:
        self.results = results
        self.calls: list[str] = []

    async def generate(self, request: AIRequest) -> AIResponse:
        provider = request.metadata["force_provider"]
        self.calls.append(provider)
        value = self.results[provider]
        if isinstance(value, Exception):
            raise value
        return AIResponse(
            text="",
            provider=provider,
            model=f"{provider}-model",
            structured={
                "answers": {QUESTION_ID: {"type": "noul", "noul": value}}
            },
        )


def _screener(gateway: _FakeGateway, providers: str = "kev,laya", **kwargs) -> LocalScreener:
    values = {
        "local_screening_enabled": True,
        "local_screening_providers": providers,
        "local_screening_confidence_threshold": 0.8,
        "mock_mode": False,
    }
    values.update(kwargs)
    return LocalScreener(
        gateway,
        settings=Settings(**values),
        mock_mode=False,
        stats=ScreeningStats(),
    )


def test_service_uses_high_confidence_answer() -> None:
    gateway = _FakeGateway({"kev": 0.95, "laya": 0.9})
    result = asyncio.run(_screener(gateway).screen("text"))
    assert result.status == "decided"
    assert result.decision is True
    assert result.provider == "kev"
    assert gateway.calls == ["kev", "laya"]


def test_service_abstains_below_threshold() -> None:
    gateway = _FakeGateway({"kev": 0.62})
    result = asyncio.run(_screener(gateway, providers="kev").screen("text"))
    assert result.status == "abstained"
    assert result.reason == "low_confidence"
    assert result.decision is None


def test_service_abstains_on_model_conflict() -> None:
    gateway = _FakeGateway({"kev": 0.95, "laya": 0.05})
    result = asyncio.run(_screener(gateway).screen("text"))
    assert result.status == "abstained"
    assert result.reason == "conflict"


def test_service_falls_through_unavailable_provider() -> None:
    gateway = _FakeGateway({
        "kev": AIError("down", kind=AIErrorKind.connection, provider="kev"),
        "laya": 0.95,
    })
    result = asyncio.run(_screener(gateway).screen("text"))
    assert result.status == "decided"
    assert result.provider == "laya"
    assert result.attempts[0].status == "unavailable"


def test_service_reports_all_providers_unavailable() -> None:
    gateway = _FakeGateway({
        "kev": AIError("down", kind=AIErrorKind.connection, provider="kev"),
        "laya": AIError("slow", kind=AIErrorKind.timeout, provider="laya"),
    })
    screener = _screener(gateway)
    result = asyncio.run(screener.screen("text"))
    assert result.status == "unavailable"
    assert screener.stats.calls == 2
    assert screener.stats.errors == 2
    assert screener.stats.timeouts == 1
    assert screener.stats.connection_errors == 1
    assert screener.stats.abstained == 1
    assert screener.stats.providers["kev"].connection_errors == 1
    assert screener.stats.providers["laya"].timeouts == 1


def test_service_abstains_on_deterministic_conflict() -> None:
    gateway = _FakeGateway({"kev": 0.95})
    result = asyncio.run(
        _screener(gateway, providers="kev").screen("text", deterministic=False)
    )
    assert result.status == "abstained"
    assert result.reason == "conflict_with_rules"


def test_service_skips_when_disabled_or_mock() -> None:
    gateway = _FakeGateway({"kev": 0.95})
    disabled_stats = ScreeningStats()
    disabled = LocalScreener(
        gateway,
        settings=Settings(mock_mode=False),
        mock_mode=False,
        stats=disabled_stats,
    )
    assert asyncio.run(disabled.screen("text")).reason == "disabled"
    mock_stats = ScreeningStats()
    mock = LocalScreener(
        gateway,
        settings=Settings(local_screening_enabled=True, mock_mode=False),
        mock_mode=True,
        stats=mock_stats,
    )
    assert asyncio.run(mock.screen("text")).reason == "mock_mode"
    assert gateway.calls == []
    for stats in (disabled_stats, mock_stats):
        assert stats.screens == 0
        assert stats.calls == 0
        assert stats.skipped == 1


def test_service_rejects_invalid_configuration() -> None:
    gateway = _FakeGateway({"kev": 0.95})
    screener = _screener(gateway, providers="kev",
                         local_screening_confidence_threshold=1.5)
    assert asyncio.run(screener.screen("text")).reason == "invalid_threshold"
    assert gateway.calls == []


def test_scope_contract_v2_replaces_v1_in_the_runtime_request() -> None:
    seen: dict = {}

    class _CaptureGateway(_FakeGateway):
        async def generate(self, request: AIRequest) -> AIResponse:
            seen.update(request.metadata)
            return await super().generate(request)

    gateway = _CaptureGateway({"kev": 0.95})
    result = asyncio.run(_screener(gateway, providers="kev").screen("text"))
    assert seen["questions"] == SCREENING_QUESTIONS_V2
    assert seen["scope_rule_version"] == SCOPE_RULE_VERSION
    assert result.scope_rule_version == SCOPE_RULE_VERSION
    assert result.as_dict()["scope_rule_version"] == SCOPE_RULE_VERSION


def test_scope_contract_v2_states_the_main_subject_rule() -> None:
    instructions = SCREENING_QUESTIONS_V2[QUESTION_ID]["instructions"]
    lowered = instructions.lower()
    assert "main subject" in lowered
    assert "passing mentions" in lowered
    assert "secondary section" in lowered
    assert "does not make the article relevant" in lowered
    assert "format" in lowered
    for domain in SCOPE_DOMAINS:
        assert domain in instructions
    assert len(SCOPE_DOMAINS) == 9
    assert SCREENING_QUESTIONS_V2[QUESTION_ID]["type"] == "noul"


def test_scope_contract_versions_stay_distinct_and_registered() -> None:
    # v1 must stay byte-identical: the stage53 dataset embeds it and the offline
    # stage55 evaluator refuses to run without it.
    assert SCREENING_QUESTIONS != SCREENING_QUESTIONS_V2
    assert question_set_version(SCREENING_QUESTIONS) == LEGACY_SCOPE_RULE_VERSION
    assert question_set_version(SCREENING_QUESTIONS_V2) == SCOPE_RULE_VERSION
    assert question_set_version({"relevant": {"type": "noul", "instructions": "?"}}) is None


def test_screening_reports_truncated_input_without_changing_the_decision() -> None:
    gateway = _FakeGateway({"kev": 0.95})
    result = asyncio.run(
        _screener(gateway, providers="kev", local_screening_max_chars=4).screen("0123456789")
    )
    assert result.status == "decided"
    assert result.decision is True
    assert result.input_chars == 10
    assert result.truncated is True
    assert result.as_dict()["truncated"] is True

    short = asyncio.run(_screener(gateway, providers="kev").screen("short text"))
    assert short.input_chars == len("short text")
    assert short.truncated is False


def test_local_screening_runtime_defaults_and_overrides(monkeypatch) -> None:
    defaults = Settings(_env_file=None)
    assert defaults.local_screening_enabled is False
    assert defaults.local_screening_timeout_seconds == 20.0
    # Stage89: the legacy 8009/8011 servers are gone; the defaults point at the
    # supervised runtimes (Kev 8123 / Laya 8124).
    assert defaults.local_screening_laya_base_url == "http://127.0.0.1:8124"
    assert defaults.local_screening_kev_base_url == "http://127.0.0.1:8123"

    monkeypatch.setenv("LOCAL_SCREENING_LAYA_BASE_URL", "http://127.0.0.1:9999")
    monkeypatch.setenv("LOCAL_SCREENING_TIMEOUT_SECONDS", "7.5")
    overridden = Settings(_env_file=None)
    assert overridden.local_screening_laya_base_url == "http://127.0.0.1:9999"
    assert overridden.local_screening_timeout_seconds == 7.5
    assert overridden.local_screening_enabled is False


# --- evaluation format ---


def _records(count: int = MIN_LABELED_SAMPLES) -> list[dict]:
    return [
        {
            "id": f"sample-{i:04d}",
            "state": f"article {i}",
            "labels": {QUESTION_ID: i % 2 == 0},
            "annotator": "test-annotator",
            "label_source": "human",
            "label_status": "valid",
            "dataset_version": "test-v1",
        }
        for i in range(count)
    ]


def test_evaluation_requires_200_human_labels() -> None:
    assert validate_records(_records()).valid
    assert not validate_records(_records(199)).valid
    bad_source = _records()
    bad_source[0]["label_source"] = "model"
    assert not validate_records(bad_source).valid
    bad_label = _records()
    bad_label[0]["labels"] = {QUESTION_ID: "yes"}
    assert not validate_records(bad_label).valid


def test_evaluation_accepts_both_question_set_versions() -> None:
    assert validate_records(_records()).valid  # v1 by default: frozen datasets stay valid

    v2 = _records()
    for row in v2:
        row["questions"] = SCREENING_QUESTIONS_V2
        row["scope_rule_version"] = SCOPE_RULE_VERSION
    assert validate_records(v2).valid

    tampered = _records()
    tampered[0]["questions"] = {
        QUESTION_ID: {"type": "noul", "instructions": "Is it interesting?"},
    }
    assert not validate_records(tampered).valid

    mislabelled = _records()
    for row in mislabelled:
        row["questions"] = SCREENING_QUESTIONS_V2
        row["scope_rule_version"] = LEGACY_SCOPE_RULE_VERSION
    check = validate_records(mislabelled)
    assert not check.valid
    assert any("scope_rule_version" in error for error in check.errors)


def test_evaluation_scores_only_supplied_predictions() -> None:
    records = _records(4)
    predictions = [1.0, 0.0, None, None]
    score = score_noul(records, predictions)
    assert score.total == 4
    assert score.scored == 2
    assert score.abstained == 2
    assert score.accuracy == 1.0
    assert score.brier == 0.0
    with pytest.raises(ValueError):
        score_noul(records, predictions[:3])


def test_evaluation_detects_duplicates_and_bad_provenance() -> None:
    duplicate_id = _records()
    duplicate_id[1]["id"] = duplicate_id[0]["id"]
    check = validate_records(duplicate_id)
    assert not check.valid
    assert check.duplicates == 1
    assert any("duplicate id" in error for error in check.errors)

    duplicate_state = _records()
    duplicate_state[1]["state"] = duplicate_state[0]["state"]
    check = validate_records(duplicate_state)
    assert not check.valid
    assert check.duplicates == 1
    assert any("duplicate state" in error for error in check.errors)

    bad_provenance = _records()
    bad_provenance[0].pop("id")
    bad_provenance[1]["label_status"] = "pending"
    bad_provenance[2]["label_source"] = "kev"
    check = validate_records(bad_provenance)
    assert not check.valid
    assert any("id is required" in error for error in check.errors)
    assert any("label_status" in error for error in check.errors)
    assert any("label_source" in error for error in check.errors)


def test_evaluation_report_contains_measured_metrics_only() -> None:
    records = _records(4)
    report = evaluate_noul(
        records,
        [0.9, 0.1, None, 0.4],
        provider="kev",
        model="kev-latest",
        errors=1,
        latencies_ms=[10.0, 20.0, None, 30.0],
    )
    assert report.total == 4
    assert report.scored == 3
    assert report.abstained == 1
    assert report.errors == 1
    assert report.accuracy == 1.0
    assert report.precision == 1.0
    assert report.recall == 1.0  # abstentions are outside the decided denominator
    assert report.brier == pytest.approx(0.06)
    assert report.coverage == 0.75
    assert report.latency_ms_total == 60.0
    assert report.latency_ms_mean == 20.0
    assert report.dataset_sha256

    decided = evaluate_noul(
        records,
        [0.9, 0.1, 0.2, 0.4],
        provider="kev",
        model="kev-latest",
    )
    assert decided.coverage == 1.0
    assert decided.recall == 0.5  # one positive was predicted negative


def test_evaluation_cli_reports_waiting_or_ready(tmp_path, capsys) -> None:
    waiting = tmp_path / "waiting.jsonl"
    waiting.write_text(
        "\n".join(json.dumps(r) for r in _records(2)), encoding="utf-8",
    )
    assert evaluation_main([str(waiting)]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "WAITING_FOR_HUMAN_LABELS"
    assert payload["human_labels"] == 2

    ready = tmp_path / "ready.jsonl"
    ready.write_text(
        "\n".join(json.dumps(r) for r in _records()),
        encoding="utf-8",
    )
    assert evaluation_main([str(ready)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "READY_FOR_EVALUATION"
    assert payload["human_labels"] == MIN_LABELED_SAMPLES
