"""Tests for ORM models & metadata (Phase 3).

این تست‌ها به دیتابیس واقعی نیاز ندارند؛ فقط ساختار metadata را بررسی می‌کنند.
"""
from __future__ import annotations

from backend.database import models as _models  # noqa: F401
from backend.database.base import Base

EXPECTED_TABLES = {
    "articles",
    "claims",
    "documents",
    "entities",
    "entity_relationships",
    "events",
    "evidence",
    "forecast_outcomes",
    "forecasts",
    "macro_observations",
    "market_observations",
    "recommendations",
    "scenarios",
    "sources",
    "world_states",
}


def test_all_expected_tables_registered() -> None:
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables.keys()))


def test_point_in_time_columns_present() -> None:
    """ستون‌های Point-in-Time باید روی Document/Article/Event وجود داشته باشند."""
    for table in ("documents", "articles", "events"):
        cols = Base.metadata.tables[table].columns
        for col in ("published_at", "retrieved_at", "available_at", "observed_at", "revision_at"):
            assert col in cols, f"{table} missing {col}"


def test_forecast_ledger_columns() -> None:
    cols = Base.metadata.tables["forecasts"].columns
    for col in ("model", "model_version", "prompt_version", "data_version", "probability"):
        assert col in cols


def test_unique_constraints() -> None:
    entity_names = {c.name for c in Base.metadata.tables["entities"].constraints}
    assert "uq_entity_type_name" in entity_names
    market_names = {c.name for c in Base.metadata.tables["market_observations"].constraints}
    assert "uq_market_obs" in market_names
