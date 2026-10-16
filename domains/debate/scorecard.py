"""Debate scorecard — مقایسه‌ی صادقانه‌ی debate با agentها و baselineها (Step 4).

- Brier/log-loss/cالیبراسیون فقط برای مدل‌های احتمالاتی (debate + agentها).
- hit rate جهتی برای همه (baselineها: expected در برابر آخرین قیمت پیش از valid_from).
- اگر پیش‌بینی‌های resolveشده کمتر از ۳۰ باشد: «نمونه ناکافی؛ نتیجه‌گیری ممنوع»، بدون برنده.
- بدون AI؛ همه‌ی محاسبات قطعی.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.forecast import Forecast, ForecastOutcome
from backend.database.models.market import MarketObservation
from domains.forecast.metrics import aggregate, parse_bool, prob_scores

logger = get_logger(__name__)

MIN_SAMPLES = 30
BASELINE_MODELS = ("baseline_naive", "baseline_historical_mean", "baseline_random_walk")
CONSENSUS_MODEL = "debate_consensus"


def _aware(dt: datetime | None) -> datetime | None:
    from datetime import UTC

    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


@dataclass
class ModelCard:
    model: str
    n: int = 0
    mean_brier: float | None = None
    mean_log_loss: float | None = None
    hit_rate: float | None = None
    calibration: list[dict] = field(default_factory=list)


@dataclass
class Scorecard:
    target: str | None
    n_resolved: int
    sufficient: bool
    verdict: str
    message: str
    cards: list[ModelCard] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "target": self.target,
            "n_resolved": self.n_resolved,
            "sufficient": self.sufficient,
            "verdict": self.verdict,
            "message": self.message,
            "cards": [
                {
                    "model": c.model, "n": c.n, "mean_brier": c.mean_brier,
                    "mean_log_loss": c.mean_log_loss, "hit_rate": c.hit_rate,
                    "calibration": c.calibration,
                }
                for c in self.cards
            ],
        }


class ScorecardBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._obs_cache: dict[str, list] = {}

    def _symbol_obs(self, symbol: str) -> list:
        """همه‌ی مشاهدات یک نماد، یک‌بار (کش حافظه‌ای برای جلوگیری از N+1)."""
        if symbol not in self._obs_cache:
            self._obs_cache[symbol] = list(self.db.execute(
                select(MarketObservation)
                .where(
                    MarketObservation.symbol == symbol,
                    MarketObservation.value.is_not(None),
                    MarketObservation.observed_at.is_not(None),
                )
                .order_by(MarketObservation.observed_at.desc())
            ).scalars().all())
        return self._obs_cache[symbol]

    def _reference_price(self, symbol: str, valid_from: datetime | None) -> float | None:
        """آخرین قیمت پیش از valid_from (در پایتون؛ سازگار با SQLite)."""
        vf = _aware(valid_from)
        if vf is None:
            return None
        for r in self._symbol_obs(symbol):
            obs = _aware(r.observed_at)
            if obs is not None and obs < vf and r.value is not None:
                return float(r.value)
        return None

    def build(self, *, target: str | None = None) -> Scorecard:
        stmt = (
            select(Forecast, ForecastOutcome)
            .join(ForecastOutcome, ForecastOutcome.forecast_id == Forecast.id)
            .where(ForecastOutcome.actual_value.is_not(None))
            .order_by(Forecast.created_at.asc())
        )
        if target:
            stmt = stmt.where(Forecast.target == target)
        rows = self.db.execute(stmt).all()

        by_model: dict[str, dict] = {}
        for fc, oc in rows:
            model = fc.model or "unknown"
            bucket = by_model.setdefault(model, {"briers": [], "logloss": [],
                                                 "hits": [], "pairs": []})
            actual = parse_bool(oc.actual_bool)
            if fc.probability is not None and actual is not None:
                ps = prob_scores(float(fc.probability), actual)
                bucket["briers"].append(ps.brier_score)
                bucket["logloss"].append(ps.log_loss)
                bucket["pairs"].append((float(fc.probability), actual))
                bucket["hits"].append(1.0 if (float(fc.probability) > 0.5) == actual else 0.0)
            elif (
                model in BASELINE_MODELS
                and fc.expected_value is not None
                and actual is not None
                and (fc.target or "").startswith("market:")
            ):
                symbol = fc.target.split(":", 1)[1]
                ref = self._reference_price(symbol, fc.valid_from)
                if ref is not None:
                    pred_up = float(fc.expected_value) > ref
                    bucket["hits"].append(1.0 if pred_up == actual else 0.0)

        cards: list[ModelCard] = []
        for model in sorted(by_model):
            b = by_model[model]
            n = len(b["hits"])
            agg = aggregate([], [], b["briers"], b["logloss"], b["pairs"])
            cards.append(ModelCard(
                model=model, n=n,
                mean_brier=agg.mean_brier, mean_log_loss=agg.mean_log_loss,
                hit_rate=round(sum(b["hits"]) / n, 4) if n else None,
                calibration=agg.calibration,
            ))

        consensus = next((c for c in cards if c.model == CONSENSUS_MODEL), None)
        n_cons = consensus.n if consensus else 0
        if n_cons < MIN_SAMPLES:
            return Scorecard(
                target=target, n_resolved=n_cons, sufficient=False,
                verdict="insufficient_sample",
                message=(f"نمونه ناکافی ({n_cons} resolveشده، حداقل {MIN_SAMPLES})؛ "
                         "نتیجه‌گیری ممنوع و برنده‌ای اعلام نمی‌شود."),
                cards=cards,
            )
        # فقط بین مدل‌های احتمالاتیِ دارای Brier
        prob_cards = [c for c in cards if c.mean_brier is not None and c.n >= MIN_SAMPLES]
        if not prob_cards:
            return Scorecard(
                target=target, n_resolved=n_cons, sufficient=False,
                verdict="insufficient_sample",
                message="هیچ مدل احتمالاتی به حد نصاب نمونه نرسید؛ نتیجه‌گیری ممنوع.",
                cards=cards,
            )
        best = min(prob_cards, key=lambda c: (c.mean_brier if c.mean_brier is not None else 9.0))
        beats_baselines = True
        base_hits = [c.hit_rate for c in cards
                     if c.model in BASELINE_MODELS and c.hit_rate is not None]
        if consensus and consensus.hit_rate is not None and base_hits:
            beats_baselines = consensus.hit_rate >= max(base_hits)
        if best.model == CONSENSUS_MODEL and beats_baselines:
            verdict, message = ("debate_wins",
                                f"debate_consensus بهترین Brier ({best.mean_brier}) و "
                                f"hit_rate رقابتی ({consensus.hit_rate if consensus else None}) دارد.")
        else:
            verdict, message = ("no_winner",
                                f"بهترین مدل احتمالاتی {best.model} است "
                                f"(Brier {best.mean_brier})؛ debate برنده نیست.")
        logger.info("scorecard | target=%s verdict=%s", target, verdict)
        return Scorecard(target=target, n_resolved=n_cons, sufficient=True,
                         verdict=verdict, message=message, cards=cards)
