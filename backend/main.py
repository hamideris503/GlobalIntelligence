"""FastAPI application factory.

ساخت اپلیکیشن، ثبت routerها، CORS و رویدادهای چرخه‌ی عمر.
در production، تنظیمات ناامن باعث fail-fast می‌شوند (بند 69).
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.ai.schemas.types import AIError
from backend.api.errors import ai_error_handler
from backend.api.routers import (
    ai,
    ai_routing,
    alerts,
    analogues,
    audit,
    briefings,
    claims,
    classify,
    debate,
    decisions,
    dedup,
    dispatch,
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
    learning,
    macro,
    markets,
    memory,
    monitoring,
    narratives,
    ops,
    outcomes,
    performance,
    portfolios,
    research,
    risk,
    scenarios,
    selfeval,
    society,
    sources,
    tournaments,
    worldstate,
)
from backend.api.routers import auth as auth_router
from backend.api.routers import local_runtimes as local_runtimes_router
from backend.api.routers import screening as screening_router
from backend.api.routers import settings as settings_router
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
    # Step 8: Gateway اعتبارنامه‌ها را از DB می‌خواند (fallback به .env)
    try:
        from backend.ai import budget as _budget
        from backend.ai import credentials_store as _store
        from backend.database.session import get_session_factory as _gsf

        _store.set_session_factory(_gsf())
        _budget.set_session_factory(_gsf())
    except Exception:  # noqa: BLE001
        logger.warning("credentials store factory not wired; .env only")
    # Phase 2: Jobهای دریافت که وسط اجرا رها شده‌اند در startup علامت‌گذاری می‌شوند
    try:
        from source_bot.jobs import recover_interrupted_jobs

        from backend.database.session import get_session_factory as _gsf_jobs

        with _gsf_jobs()() as _db:
            recover_interrupted_jobs(_db)
    except Exception:  # noqa: BLE001 — بدون DB هم سرور باید بالا بیاید
        logger.warning("ingest job recovery skipped (db unavailable)")

    # Stage89: recover abandoned dispatch leases and decisions that have no
    # dispatch rows, then start the bounded in-process consumer.
    dispatch_stop: asyncio.Event | None = None
    dispatch_task: asyncio.Task | None = None
    try:
        from backend.ai.dispatch.runner import recover_at_startup, run_forever
        from backend.database.session import get_session_factory as _gsf_dispatch

        with _gsf_dispatch()() as _db:
            recovered = recover_at_startup(_db)
        if recovered["stale"] or recovered["reenqueued"]:
            logger.warning("dispatch recovery | %s", recovered)
        if settings.dispatch_auto_run:
            dispatch_stop = asyncio.Event()
            dispatch_task = asyncio.create_task(
                run_forever(
                    dispatch_stop,
                    interval=settings.dispatch_poll_seconds,
                    limit=settings.dispatch_batch_limit,
                )
            )
    except Exception:  # noqa: BLE001 — dispatch must not block startup
        logger.warning("dispatch startup skipped (db or migration unavailable)")
    yield
    if dispatch_stop is not None and dispatch_task is not None:
        dispatch_stop.set()
        with suppress(Exception):
            await asyncio.wait_for(dispatch_task, timeout=5)
        if not dispatch_task.done():  # pragma: no cover - defensive
            dispatch_task.cancel()
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

    # خطاهای ساختاریافته‌ی AI → وضعیت HTTP معنادار (بقیه‌ی exceptionها پیش‌فرض می‌مانند)
    app.add_exception_handler(AIError, ai_error_handler)

    # /health بدون احراز هویت (برای probe)، لاگین هم عمومی است (خودش ورود است)
    app.include_router(health.router)
    app.include_router(auth_router.router)
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
    app.include_router(debate.router, dependencies=protected)
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
    app.include_router(ops.router, dependencies=protected)
    app.include_router(monitoring.router, dependencies=protected)
    app.include_router(portfolios.router, dependencies=protected)
    app.include_router(performance.router, dependencies=protected)
    app.include_router(forecasts.router, dependencies=protected)
    app.include_router(evaluation.router, dependencies=protected)
    app.include_router(tournaments.router, dependencies=protected)
    app.include_router(scenarios.router, dependencies=protected)
    app.include_router(selfeval.router, dependencies=protected)
    app.include_router(settings_router.router, dependencies=protected)
    app.include_router(dispatch.router, dependencies=protected)
    app.include_router(local_runtimes_router.router, dependencies=protected)
    app.include_router(screening_router.router, dependencies=protected)
    app.include_router(research.router, dependencies=protected)
    app.include_router(risk.router, dependencies=protected)
    app.include_router(decisions.router, dependencies=protected)
    app.include_router(learning.router, dependencies=protected)
    app.include_router(iran.router, dependencies=protected)
    return app


app = create_app()
