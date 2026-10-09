"""FastAPI application factory.

ساخت اپلیکیشن، ثبت routerها، CORS و رویدادهای چرخه‌ی عمر.
در production، تنظیمات ناامن باعث fail-fast می‌شوند (بند 69).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import (
    ai,
    analogues,
    claims,
    classify,
    dedup,
    economic,
    events,
    forecasts,
    geopolitics,
    graph,
    health,
    independence,
    ingestion,
    jobs,
    macro,
    markets,
    memory,
    narratives,
    outcomes,
    society,
    sources,
    worldstate,
)
from backend.auth.deps import require_api_key
from backend.core.config import get_settings
from backend.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.validate_production()
    logger.info(
        "startup | app=%s env=%s mock_mode=%s",
        settings.app_name,
        settings.app_env,
        settings.mock_mode,
    )
    yield
    logger.info("shutdown | app=%s", settings.app_name)


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Global Intelligence, Economic Research, Forecasting & Decision Support Platform",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # /health بدون احراز هویت (برای probe)، بقیه محافظت‌شده
    app.include_router(health.router)
    protected = [Depends(require_api_key)]
    app.include_router(jobs.router, dependencies=protected)
    app.include_router(ai.router, dependencies=protected)
    app.include_router(sources.router, dependencies=protected)
    app.include_router(ingestion.router, dependencies=protected)
    app.include_router(dedup.router, dependencies=protected)
    app.include_router(classify.router, dependencies=protected)
    app.include_router(events.router, dependencies=protected)
    app.include_router(claims.router, dependencies=protected)
    app.include_router(independence.router, dependencies=protected)
    app.include_router(graph.router, dependencies=protected)
    app.include_router(economic.router, dependencies=protected)
    app.include_router(markets.router, dependencies=protected)
    app.include_router(worldstate.router, dependencies=protected)
    app.include_router(memory.router, dependencies=protected)
    app.include_router(analogues.router, dependencies=protected)
    app.include_router(macro.router, dependencies=protected)
    app.include_router(geopolitics.router, dependencies=protected)
    app.include_router(society.router, dependencies=protected)
    app.include_router(narratives.router, dependencies=protected)
    app.include_router(outcomes.router, dependencies=protected)
    app.include_router(forecasts.router, dependencies=protected)
    return app


app = create_app()
