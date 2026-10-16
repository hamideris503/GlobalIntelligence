"""Debate engine — اجرای دورها، ذخیره، ثبت Ledger (Step 3)."""
from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.ai.gateway import get_gateway
from backend.ai.schemas.types import AIRequest, Message
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.database.models.debate import DebateMessage, DebateRun
from backend.database.models.forecast import Forecast
from backend.database.models.model_performance import ModelPerformance
from domains.audit.service import log_action
from domains.debate.agents import (
    AGENT_ROLES,
    AGENT_SCHEMA,
    AGENTS,
    QUANT_AGENT,
    REPORT_AGENT,
    AgentResult,
    clip_probability,
    normalize_output,
    validate_agent_dict,
)
from domains.debate.aggregate import aggregate, quant_anchor_probability
from domains.debate.context import ContextPack, build_context_pack
from domains.debate.prompts import (
    PROMPT_VERSION,
    repair_prompt,
    report_prompt,
    round1_prompt,
    round2_prompt,
)

logger = get_logger(__name__)

MODEL_VERSION = "debate_v1"
MAX_ROUNDS_HARD = 5

# کالیبراسیون برآورد dry-run (Step 9؛ اندازه‌گیری واقعی، نه حدس):
# run 48635825 (market:WTI، ۵ agent، ۲ دور): برآورد خام ۲۶٬۵۸۰ → واقعی ۵۵٬۷۰۳.
# علت اختلاف: retryهای تعمیری + پرامپت بزرگ‌تر دور ۲ + گزارش. n=1 (موقت)؛
# با اجراهای بعدی بازبینی شود.
CALIBRATION_FACTOR = 2.1
# سهم اندازه‌گیری‌شده‌ی هر بخش از کل توکن (همان run)
SHARE_R1 = 0.415
SHARE_R2 = 0.567
SHARE_REPORT = 0.018


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _safe_json(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:  # noqa: BLE001
                return None
        return None


def _validate_schema(data: dict) -> None:
    try:
        import jsonschema

        jsonschema.validate(instance=data, schema=AGENT_SCHEMA)
    except ImportError:
        logger.warning("jsonschema not installed; minimal validation only")
        validate_agent_dict("agent", data)
    except Exception as exc:
        raise ValueError(f"agent schema invalid: {exc}") from exc


@dataclass
class AgentCall:
    agent: str
    result: AgentResult | None = None
    provider: str = ""
    model: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost_estimate: float | None = None
    latency_ms: float | None = None
    prompt_hash: str = ""
    raw_text: str = ""
    error: str | None = None


@dataclass
class DebateOutcome:
    run_id: str | None = None
    status: str = "failed"
    consensus: float | None = None
    disagreement: float | None = None
    confidence: float | None = None
    forecast_ids: list[str] = field(default_factory=list)
    total_tokens: int = 0
    total_cost: float | None = None
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "run_id": self.run_id, "status": self.status,
            "consensus": self.consensus, "disagreement": self.disagreement,
            "confidence": self.confidence, "forecast_ids": self.forecast_ids,
            "total_tokens": self.total_tokens, "total_cost": self.total_cost,
            "errors": self.errors,
        }


def load_debate_config() -> dict:
    """خواندن config/debate.toml (fallback به پیش‌فرض‌ها)."""
    import os
    import tomllib

    defaults = {
        "targets": [{"target": "market:WTI", "horizon_days": 30}],
        "max_rounds": 2,
        "agents": {},
        "max_events": 15,
    }
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config", "debate.toml",
    )
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
        return {
            "targets": [t for t in data.get("targets", {}).get("list", []) if t.get("target")],
            "max_rounds": int(data.get("rounds", {}).get("max_rounds", 2)),
            "agents": data.get("agents", {}),
            "max_events": int(data.get("context", {}).get("max_events", 15)),
        } or defaults
    except Exception:  # noqa: BLE001
        return defaults


def resolve_agent_model(agent: str, agent_cfg: dict) -> tuple[str, str | None]:
    """(provider, model|None) از toml + .env؛ خالی یعنی پیش‌فرض Provider."""
    settings = get_settings()
    cfg = agent_cfg.get(agent, {}) if isinstance(agent_cfg, dict) else {}
    provider = str(cfg.get("provider", "mock"))
    env_name = str(cfg.get("model_env", ""))
    model = None
    if env_name:
        value = getattr(settings, env_name.lower(), None)
        if isinstance(value, str) and value.strip():
            model = value.strip()
    return provider, model


def resolve_agent_route(agent: str, agent_cfg: dict) -> tuple[str, str | None]:
    """اولویت: نگاشت DB (agent_assignments) و بعد toml/.env (Step 8)."""
    try:
        from backend.ai import credentials_store as store

        mapping = store.get_agent_mapping()
    except Exception:  # noqa: BLE001
        mapping = {}
    if agent in mapping:
        return mapping[agent]
    return resolve_agent_model(agent, agent_cfg)


class DebateEngine:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.gateway = get_gateway()
        self.settings = get_settings()
        self.cfg = load_debate_config()

    # --- budget ---
    def spent_today_usd(self) -> float:
        total = self.db.execute(
            select(func.coalesce(func.sum(DebateMessage.cost_estimate), 0.0)).where(
                func.date(DebateMessage.created_at) == func.current_date()
            )
        ).scalars().one()
        return float(total or 0.0)

    def _past_briers(self) -> dict[str, tuple[float, int]]:
        """میانگین Brier هر مدل debate از model_performance (model, n)."""
        out: dict[str, tuple[float, int]] = {}
        rows = self.db.execute(select(ModelPerformance)).scalars().all()
        for r in rows:
            if (r.model or "").startswith("debate:") and r.mean_brier is not None:
                out[r.model] = (float(r.mean_brier), int(r.n_scored or 0))
        return out

    async def _call_agent(
        self, *, agent: str, prompt: str, context_json: str,
        valid_refs: set[str], temperature: float = 0.3,
    ) -> AgentCall:
        provider, model = resolve_agent_route(agent, self.cfg.get("agents", {}))
        metadata: dict = {"prompt_version": PROMPT_VERSION, "force_provider": provider}
        if model:
            metadata["model"] = model
        request = AIRequest(
            messages=[
                Message.system("You output strict JSON compatible with the schema."),
                Message.user(prompt),
            ],
            role="deep_analysis" if agent != "risk_critic" else "critic",
            task=f"debate_{agent}",
            temperature=temperature,
            json_schema=AGENT_SCHEMA,
            metadata=metadata,
        )
        call = AgentCall(agent=agent, provider=provider, model=model or "")
        try:
            resp = await self.gateway.generate(request)
        except Exception as exc:  # noqa: BLE001
            # FALLBACK مستند: یک retry با مدل پیش‌فرض Provider، بعد حذف agent با ثبت خطا
            logger.warning("debate agent %s failed (%s); retry with default model", agent, type(exc).__name__)
            try:
                fallback_req = AIRequest(
                    messages=request.messages, role=request.role, task=request.task,
                    temperature=request.temperature, json_schema=AGENT_SCHEMA,
                    metadata={"prompt_version": PROMPT_VERSION},
                )
                resp = await self.gateway.generate(fallback_req)
            except Exception as exc2:  # noqa: BLE001
                call.error = f"{type(exc2).__name__}: {str(exc2)[:200]}"
                return call
        call.provider = resp.provider
        call.model = resp.model
        prompt_tokens = resp.usage.prompt_tokens or 0
        completion_tokens = resp.usage.completion_tokens or 0
        call.latency_ms = resp.latency_ms
        call.prompt_hash = _hash(prompt)
        call.raw_text = resp.text
        data = _safe_json(resp.text)
        if not isinstance(data, dict):
            # یک repair retry با دستور صریح
            repair = AIRequest(
                messages=[
                    Message.system("You output ONLY a JSON object per the schema."),
                    Message.user(repair_prompt(context_json=context_json)),
                ],
                role=request.role, task=request.task, temperature=0.0,
                json_schema=AGENT_SCHEMA, metadata=metadata,
            )
            try:
                resp2 = await self.gateway.generate(repair)
                call.raw_text = resp2.text
                prompt_tokens += resp2.usage.prompt_tokens or 0
                completion_tokens += resp2.usage.completion_tokens or 0
                data = _safe_json(resp2.text)
            except Exception as exc:  # noqa: BLE001
                call.error = f"{type(exc).__name__}: {str(exc)[:200]}"
                return call
        if not isinstance(data, dict):
            call.error = "non-JSON output after 1 repair retry"
            return call
        data = normalize_output(data)
        try:
            _validate_schema(data)
            call.result = AgentResult.from_dict(agent, data, valid_refs)
        except ValueError:
            # FALLBACK مستند (مشابه classifier): یک repair retry با یادآوری صریح schema
            logger.warning("debate agent %s schema-invalid; one repair retry", agent)
            repair2 = AIRequest(
                messages=[
                    Message.system(
                        "You output ONLY a JSON object with EXACTLY these required keys: "
                        "direction, probability_up, horizon_days, confidence, "
                        "key_evidence, assumptions, invalidation_conditions, uncertainties. "
                        "No prose, no markdown fences."
                    ),
                    Message.user(repair_prompt(context_json=context_json)),
                ],
                role=request.role, task=request.task, temperature=0.0,
                json_schema=AGENT_SCHEMA, metadata=metadata,
            )
            try:
                resp3 = await self.gateway.generate(repair2)
                call.raw_text = resp3.text
                prompt_tokens += resp3.usage.prompt_tokens or 0
                completion_tokens += resp3.usage.completion_tokens or 0
                data = _safe_json(resp3.text)
            except Exception as exc:  # noqa: BLE001
                call.error = f"{type(exc).__name__}: {str(exc)[:200]}"
                return call
            if not isinstance(data, dict):
                call.error = "non-JSON output after repair retries"
                return call
            data = normalize_output(data)
            try:
                _validate_schema(data)
                call.result = AgentResult.from_dict(agent, data, valid_refs)
            except ValueError as exc:
                call.error = str(exc)[:300]
        # Step 8: توکن‌های همه‌ی تلاش‌ها + هزینه از قیمت ثبت‌شده
        call.prompt_tokens = prompt_tokens or None
        call.completion_tokens = completion_tokens or None
        call.total_tokens = (prompt_tokens + completion_tokens) or None
        try:
            from backend.ai import credentials_store as store

            price = store.find_price(provider, model or call.model)
            computed = store.compute_cost(prompt_tokens, completion_tokens, price)
        except Exception:  # noqa: BLE001
            computed = None
        call.cost_estimate = computed
        return call

    def _quant_call(self, pack: ContextPack) -> AgentCall:
        p = quant_anchor_probability(pack.baselines, pack.reference_price)
        result = AgentResult(
            agent=QUANT_AGENT, direction="up" if p > 0.5 else ("down" if p < 0.5 else "flat"),
            probability_up=clip_probability(p), horizon_days=30, confidence=0.5,
            assumptions=["statistical anchor only: mean of baseline expected values vs reference"],
            invalidation_conditions=["baseline recomputation changes the mean side"],
            uncertainties=["baselines ignore regime breaks"],
        )
        return AgentCall(agent=QUANT_AGENT, result=result, provider="none", model="quant_v1")

    def _cost_ceiling_lines(self, rounds: int, est_tokens: int) -> str:
        """سقف هزینه‌ی dry-run از قیمت‌های ثبت‌شده (نه پیش‌بینی).

        سهم توکن هر agent از اندازه‌گیری واقعی × گران‌ترین نرخش؛
        خروجی سقف است نه پیش‌بینی. agent بدون قیمت → ذکر می‌شود.
        """
        try:
            from backend.ai import credentials_store as store
        except Exception:  # noqa: BLE001
            return ""
        share_each = ((SHARE_R1 if rounds >= 1 else 0.0)
                      + (SHARE_R2 if rounds >= 2 else 0.0)) / len(AGENTS)
        parts = []
        ceiling = 0.0
        missing = []
        for a in AGENTS:
            prov, mod = resolve_agent_route(a, self.cfg.get("agents", {}))
            price = store.find_price(prov, mod)
            if price is None or (price[0] is None and price[1] is None):
                missing.append(f"{a}={prov}/{mod or '?'}")
                continue
            rate = max(price[0] or 0.0, price[1] or 0.0)
            ceiling += share_each * est_tokens * rate / 1e6
            parts.append(f"{a}={mod or '?'}")
        out = f"cost ceiling ~= ${ceiling:.4f} ({', '.join(parts)})" if parts else ""
        if missing:
            out += ("; " if out else "") + "no price: " + ", ".join(missing)
        return out

    async def run(
        self, *, target: str, horizon_days: int = 30,
        dry_run: bool = False, max_rounds: int | None = None,
    ) -> DebateOutcome:
        outcome = DebateOutcome()
        rounds = min(max_rounds or self.settings.debate_max_rounds,
                     self.cfg.get("max_rounds", 2), MAX_ROUNDS_HARD)
        rounds = max(1, rounds)

        pack = build_context_pack(
            self.db, target=target, horizon_days=horizon_days,
            max_events=self.cfg.get("max_events", 15),
        )
        if pack.insufficient_reason and pack.reference_price is None:
            outcome.status = "insufficient_evidence"
            outcome.errors.append(pack.insufficient_reason)
            self._persist_empty(target, horizon_days, pack, outcome)
            return outcome

        context_json = json.dumps({
            "target": pack.target, "target_date": pack.target_date.isoformat(),
            "as_of": pack.as_of.isoformat(), "reference_price": pack.reference_price,
            "reference_at": pack.reference_at, "changes_pct": pack.changes_pct,
            "baselines": pack.baselines, "world_state": pack.world_state,
            "events": pack.events, "claims": pack.claims, "macro": pack.macro,
        }, ensure_ascii=False)[:12000]

        # برآورد توکن dry-run (تخمینی، لیبل‌دار، کالیبره‌شده با اندازه‌گیری واقعی)
        raw_tokens = (len(context_json) // 4) * (len(AGENTS) * rounds + 2)
        est_tokens = int(raw_tokens * CALIBRATION_FACTOR)
        if dry_run:
            outcome.status = "dry_run"
            outcome.total_tokens = est_tokens
            ceiling_lines = self._cost_ceiling_lines(rounds, est_tokens)
            outcome.errors.append(
                f"estimate only: raw ~{raw_tokens} x{CALIBRATION_FACTOR} = "
                f"~{est_tokens} tokens (calibrated on 1 real run: 26580 -> 55703)"
                + ("; " + ceiling_lines if ceiling_lines else "")
            )
            return outcome
        if est_tokens > self.settings.debate_max_tokens_per_run:
            outcome.status = "budget_stopped"
            outcome.errors.append(
                f"estimated {est_tokens} tokens > DEBATE_MAX_TOKENS_PER_RUN="
                f"{self.settings.debate_max_tokens_per_run}"
            )
            self._persist_empty(target, horizon_days, pack, outcome)
            return outcome
        spent = self.spent_today_usd()
        if spent >= self.settings.debate_daily_budget_usd:
            outcome.status = "budget_stopped"
            outcome.errors.append(
                f"daily budget exhausted: spent ~{spent:.4f} USD >= "
                f"{self.settings.debate_daily_budget_usd}"
            )
            self._persist_empty(target, horizon_days, pack, outcome)
            return outcome

        # Step 8: اگر قیمت مدلی ثبت نشده، با هشدار price_missing توقف (نه cost=NULL)
        try:
            from backend.ai import credentials_store as store

            missing = []
            for a in AGENTS:
                prov, mod = resolve_agent_route(a, self.cfg.get("agents", {}))
                if store.find_price(prov, mod) is None:
                    missing.append(f"{a}={prov}/{mod or '?'}")
        except Exception:  # noqa: BLE001
            missing = []
        if missing:
            outcome.status = "price_missing"
            outcome.errors.append(
                "no registered price for: " + ", ".join(missing)
                + " — register model prices in settings first"
            )
            self._persist_empty(target, horizon_days, pack, outcome)
            return outcome

        # دور ۱ (مستقل؛ ترتیبی با مکث قابل‌تنظیم برای سهمیه‌ی free-tier)
        calls_r1: list[AgentCall] = []
        for a in AGENTS:
            calls_r1.append(await self._call_agent(
                agent=a, context_json=context_json, valid_refs=pack.valid_refs(),
                prompt=round1_prompt(
                    agent=a, role=AGENT_ROLES[a], target=target,
                    target_date=pack.target_date.date().isoformat(),
                    context_json=context_json),
            ))
            if self.settings.debate_call_gap_seconds > 0:
                await asyncio.sleep(self.settings.debate_call_gap_seconds)
        results: dict[str, AgentResult] = {
            c.agent: c.result for c in calls_r1 if c.result is not None
        }
        all_calls: list[tuple[int, AgentCall]] = [(1, c) for c in calls_r1]

        # دور ۲ (نقد) — فقط اگر حداقل ۲ agent موفق بودند
        if rounds >= 2 and len(results) >= 2:
            r1_json = {
                c.agent: (c.raw_text[:2000] if c.result else f"ERROR: {c.error}")
                for c in calls_r1
            }
            calls_r2: list[AgentCall] = []
            for c in calls_r1:
                if c.result is None:
                    continue
                calls_r2.append(await self._call_agent(
                    agent=c.agent, context_json=context_json,
                    valid_refs=pack.valid_refs(),
                    prompt=round2_prompt(
                        agent=c.agent, role=AGENT_ROLES[c.agent], target=target,
                        target_date=pack.target_date.date().isoformat(),
                        context_json=context_json,
                        others_json=json.dumps(
                            {k: v for k, v in r1_json.items() if k != c.agent},
                            ensure_ascii=False)[:6000],
                        own_json=r1_json[c.agent][:2000]),
                ))
                if self.settings.debate_call_gap_seconds > 0:
                    await asyncio.sleep(self.settings.debate_call_gap_seconds)
            for c in calls_r2:
                if c.result is not None:
                    results[c.agent] = c.result
            all_calls += [(2, c) for c in calls_r2]

        # لنگر کمی (بدون LLM)
        quant = self._quant_call(pack)
        results[QUANT_AGENT] = quant.result  # type: ignore[assignment]
        all_calls.append((1, quant))

        llm_ok = [a for a in results if a != QUANT_AGENT]
        if not llm_ok:
            # هیچ agent واقعی موفق نشد؛ اجماع تک‌لنگر گمراه‌کننده است
            outcome.status = "failed"
            outcome.errors.append("all LLM agents failed (only quant anchor available)")
            self._persist_empty(target, horizon_days, pack, outcome)
            return outcome

        if not results:
            outcome.status = "failed"
            outcome.errors.append("all agents failed")
            self._persist_empty(target, horizon_days, pack, outcome)
            return outcome

        probs = {a: r.probability_up for a, r in results.items()}
        qualities = {a: r.quality_score for a, r in results.items()}
        agg = aggregate(probs, qualities, self._past_briers())

        # گزارش‌نویس (فقط متن)
        narrative = ""
        try:
            rep_provider, rep_model = resolve_agent_model(REPORT_AGENT, self.cfg.get("agents", {}))
            rep_meta: dict = {"prompt_version": PROMPT_VERSION}
            if rep_model:
                rep_meta["model"] = rep_model
            rep_resp = await self.gateway.generate(AIRequest(
                messages=[Message.user(report_prompt(
                    target=target, consensus=agg.consensus_probability,
                    disagreement=agg.disagreement,
                    agents_json=json.dumps(
                        {a: {"p": r.probability_up, "conf": r.confidence,
                             "assumptions": r.assumptions[:3],
                             "invalidation": r.invalidation_conditions[:3]}
                         for a, r in results.items()}, ensure_ascii=False)[:6000]))],
                role="report", task="debate_report", temperature=0.4,
                metadata=rep_meta,
            ))
            narrative = rep_resp.text[:4000]
            all_calls.append((rounds, AgentCall(
                agent=REPORT_AGENT, provider=rep_provider, model=rep_resp.model,
                prompt_tokens=rep_resp.usage.prompt_tokens,
                completion_tokens=rep_resp.usage.completion_tokens,
                total_tokens=rep_resp.usage.total_tokens,
                cost_estimate=rep_resp.cost_estimate, latency_ms=rep_resp.latency_ms,
                raw_text=narrative)))
        except Exception as exc:  # noqa: BLE001
            logger.warning("debate report failed: %s", type(exc).__name__)

        outcome.status = "done"
        outcome.consensus = agg.consensus_probability
        outcome.disagreement = agg.disagreement
        outcome.confidence = agg.confidence
        self._persist(target, horizon_days, pack, agg, results, all_calls, narrative, outcome)
        return outcome

    def _persist_empty(self, target: str, horizon_days: int, pack: ContextPack,
                       outcome: DebateOutcome) -> None:
        run = DebateRun(target=target, horizon_days=horizon_days,
                        target_date=pack.target_date, status=outcome.status,
                        context_hash=pack.context_hash)
        self.db.add(run)
        self.db.commit()
        outcome.run_id = str(run.id)
        log_action(self.db, action="debate_run", actor="engine", target_type="debate_run",
                   target_id=str(run.id),
                   params={"target": target, "status": outcome.status},
                   result=outcome.as_dict(), status="ok")

    def _persist(self, target: str, horizon_days: int, pack: ContextPack,
                 agg: Any, results: dict[str, AgentResult],
                 all_calls: list[tuple[int, AgentCall]], narrative: str,
                 outcome: DebateOutcome) -> None:
        total_tokens = sum((c.total_tokens or 0) for _, c in all_calls)
        costs = [(c.cost_estimate or 0.0) for _, c in all_calls]
        total_cost = round(sum(costs), 6) if any(c.cost_estimate for _, c in all_calls) else None
        run = DebateRun(
            target=target, horizon_days=horizon_days, target_date=pack.target_date,
            status="done", context_hash=pack.context_hash,
            reference_price=pack.reference_price,
            consensus_probability=agg.consensus_probability,
            disagreement=agg.disagreement, confidence=agg.confidence,
            context_pack=json.dumps({
                "events": pack.events, "claims": pack.claims,
                "reference_price": pack.reference_price,
            }, ensure_ascii=False)[:20000],
            total_tokens=total_tokens,
            total_cost_estimate=total_cost,
        )
        self.db.add(run)
        self.db.flush()
        for round_no, c in all_calls:
            self.db.add(DebateMessage(
                run_id=run.id, round_no=round_no, agent=c.agent,
                provider=c.provider or None, model=c.model or None,
                prompt_version=PROMPT_VERSION, prompt_hash=c.prompt_hash or None,
                response_text=(c.raw_text or "")[:8000] or None,
                probability_up=(c.result.probability_up if c.result else None),
                confidence=(c.result.confidence if c.result else None),
                quality_score=(c.result.quality_score if c.result else None),
                prompt_tokens=c.prompt_tokens, completion_tokens=c.completion_tokens,
                total_tokens=c.total_tokens, cost_estimate=c.cost_estimate,
                latency_ms=c.latency_ms, error=c.error,
            ))
        # ثبت Ledger: هر agent + اجماع (افزودنی؛ ردیف قدیمی حذف نمی‌شود)
        assert pack.target_date is not None
        for agent, r in results.items():
            fc = Forecast(
                valid_from=pack.as_of, target_date=pack.target_date,
                horizon="short" if horizon_days <= 45 else ("medium" if horizon_days <= 200 else "long"),
                target=target, probability=r.probability_up,
                expected_value=None, confidence=r.confidence,
                model=f"debate:{agent}:{self._model_of(all_calls, agent)}",
                model_version=MODEL_VERSION, prompt_version=PROMPT_VERSION,
                data_version=pack.context_hash, status="active",
                evidence=json.dumps({
                    "debate_run": str(run.id), "agent": agent,
                    "ref_ids": [e["ref_id"] for e in r.key_evidence],
                    "rejected_refs": r.rejected_refs,
                    "reference_price": pack.reference_price,
                    "reference_at": pack.reference_at,
                }, ensure_ascii=False),
                assumptions=json.dumps(r.assumptions, ensure_ascii=False),
            )
            self.db.add(fc)
            self.db.flush()
            outcome.forecast_ids.append(str(fc.id))
        consensus_fc = Forecast(
            valid_from=pack.as_of, target_date=pack.target_date,
            horizon="short" if horizon_days <= 45 else ("medium" if horizon_days <= 200 else "long"),
            target=target, probability=agg.consensus_probability,
            expected_value=None, confidence=agg.confidence,
            model="debate_consensus", model_version=MODEL_VERSION,
            prompt_version=PROMPT_VERSION, data_version=pack.context_hash,
            status="active",
            evidence=json.dumps({
                "debate_run": str(run.id),
                "weights": agg.weights, "disagreement": agg.disagreement,
                "narrative": narrative,
                "reference_price": pack.reference_price,
                "reference_at": pack.reference_at,
            }, ensure_ascii=False),
            assumptions="deterministic log-odds aggregation; see ADR-STEP3",
        )
        self.db.add(consensus_fc)
        self.db.flush()
        outcome.forecast_ids.append(str(consensus_fc.id))
        outcome.run_id = str(run.id)
        outcome.total_tokens = total_tokens
        outcome.total_cost = total_cost
        self.db.commit()
        log_action(self.db, action="debate_run", actor="engine", target_type="debate_run",
                   target_id=str(run.id),
                   params={"target": target, "agents": sorted(results)},
                   result=outcome.as_dict(), status="ok")

    @staticmethod
    def _model_of(all_calls: list[tuple[int, AgentCall]], agent: str) -> str:
        for _, c in all_calls:
            if c.agent == agent and c.model:
                return c.model
        return "unknown"
