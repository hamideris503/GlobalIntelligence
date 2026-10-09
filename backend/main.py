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
    ai_routing,
    alerts,
    analogues,
    audit,
    briefings,
    claims,
    classify,
    decisions,
    dedup,
    economic,
    evaluation,
    events,
    forecasts,
    geopolitics,
    graph,
    health,
    independence,
    ingestion,
    iran,
    jobs,
    macro,
    markets,
    memory,
    narratives,
    outcomes,
    performance,
    portfolios,
    risk,
    scenarios,
    selfeval,
    society,
    sources,
    tournaments,
    worldstate,
)
from backend.auth.deps import require_api_key
from backend.core.config import get_settings
from backend.core.logging import configure_logging, get_logger
from backend.core.security import RateLimitMiddleware, SecurityHeadersMiddleware

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
    is_prod = settings.app_env == "production"

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Global Intelligence, Economic Research, Forecasting & Decision Support Platform",
        lifespan=lifespan,
        # مستندات تعاملی در production عمومی نیست (Phase 44)
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )

    if settings.rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware, per_minute=settings.rate_limit_per_minute
        )
    # هدرهای امنیتی بیرونی‌ترین لایه‌اند تا روی 429 هم بنشینند
    app.add_middleware(SecurityHeadersMiddleware)

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
    app.include_router(ai_routing.router, dependencies=protected)
    app.include_router(alerts.router, dependencies=protected)
    app.include_router(audit.router, dependencies=protected)
    app.include_router(briefings.router, dependencies=protected)
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
    app.include_router(portfolios.router, dependencies=protected)
    app.include_router(performance.router, dependencies=protected)
    app.include_router(forecasts.router, dependencies=protected)
    app.include_router(evaluation.router, dependencies=protected)
    app.include_router(tournaments.router, dependencies=protected)
    app.include_router(scenarios.router, dependencies=protected)
    app.include_router(selfeval.router, dependencies=protected)
    app.include_router(risk.router, dependencies=protected)
    app.include_router(decisions.router, dependencies=protected)
    app.include_router(iran.router, dependencies=protected)
    return app


app = create_app()
