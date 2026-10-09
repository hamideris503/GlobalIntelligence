"""Tournament Engine — رقابت مدل‌ها روی اهداف مشترک (Phase 29).

مسیر هر (هدف، روش): forecast → resolve → evaluate → تجمیع هر مدل → رتبه‌بندی.

قانون رتبه‌بندی (v1, مستند):
- معیار اصلی MAE (پیش‌بینی‌های مقداری)؛ اگر MAE نبود، mean_brier؛
  تساوی → تعداد امتیاز بیشتر؛ هیچ امتیازی → برنده None (صادقانه).
- رکورد تورنمنت با leaderboard کامل ذخیره می‌شود (تاریخچه‌ی رقابت).
- بدون AI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.tournament import Tournament
from domains.forecast.engine import ForecastEngine
from domains.forecast.evaluation import EvaluationEngine
from domains.forecast.outcome import OutcomeEngine

logger = get_logger(__name__)


@dataclass
class TournamentOutcome:
    tournament_id: str = ""
    name: str = ""
    board: list[dict] = field(default_factory=list)
    winner_model: str | None = None
    n_forecasts: int = 0

    def as_dict(self) -> dict:
        return {
            "tournament_id": self.tournament_id,
            "name": self.name,
            "board": self.board,
            "winner_model": self.winner_model,
            "n_forecasts": self.n_forecasts,
        }


def rank_key(row: dict) -> tuple:
    """کلید رتبه: MAE کمتر بهتر؛ وگرنه brier؛ تساوی با تعداد بیشتر."""
    mae = row.get("mae")
    brier = row.get("mean_brier")
    n = row.get("n_scored", 0)
    if mae is not None:
        return (0, mae, -n)
    if brier is not None:
        return (1, brier, -n)
    return (2, 0.0, -n)


class TournamentEngine:
    def __init__(self, db: Session) -> None:
        self.db = db

    def run(
        self,
        *,
        targets: list[str],
        methods: list[str] | None = None,
        horizon: str = "short",
        scenario: str = "base",
        name: str | None = None,
    ) -> TournamentOutcome:
        methods = methods or ["naive", "historical_mean", "random_walk"]
        forecast_engine = ForecastEngine(self.db)
        outcome_engine = OutcomeEngine(self.db)
        evaluation_engine = EvaluationEngine(self.db)

        n_forecasts = 0
        for target in targets:
            for method in methods:
                try:
                    res = forecast_engine.run(
                        target=target,
                        method=method,
                        horizon=horizon,
                        scenario=scenario,
                    )
                    n_forecasts += res.created
                except Exception:  # noqa: BLE001
                    logger.warning("tournament forecast failed | %s %s", target, method)
            try:
                outcome_engine.resolve_all(target=target)
                evaluation_engine.run(target=target)
            except Exception:  # noqa: BLE001
                logger.warning("tournament resolve/evaluate failed | %s", target)

        board: list[dict] = []
        for method in methods:
            model = f"baseline_{method}"
            agg = evaluation_engine.summary(targets=targets, model=model)
            board.append(
                {
                    "model": model,
                    "n_scored": agg["n"],
                    "mae": agg["mae"],
                    "rmse": agg["rmse"],
                    "mean_brier": agg["mean_brier"],
                    "mean_log_loss": agg["mean_log_loss"],
                }
            )
        board.sort(key=rank_key)
        winner = board[0]["model"] if board and board[0].get("mae") is not None else None
        # brier-only winner
        if winner is None and board and board[0].get("mean_brier") is not None:
            winner = board[0]["model"]

        now = datetime.now(UTC)
        tournament = Tournament(
            name=name or f"tournament-{now.strftime('%Y%m%d-%H%M')}",
            targets=json.dumps(targets, ensure_ascii=False),
            methods=json.dumps(methods, ensure_ascii=False),
            horizon=horizon,
            results=json.dumps(board, ensure_ascii=False),
            winner_model=winner,
            n_forecasts=n_forecasts,
            observed_at=now,
        )
        self.db.add(tournament)
        self.db.commit()
        self.db.refresh(tournament)
        logger.info(
            "tournament done | name=%s winner=%s n=%d",
            tournament.name, winner, n_forecasts,
        )
        return TournamentOutcome(
            tournament_id=str(tournament.id),
            name=tournament.name,
            board=board,
            winner_model=winner,
            n_forecasts=n_forecasts,
        )
