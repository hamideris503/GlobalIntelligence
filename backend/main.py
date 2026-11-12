"""FastAPI application factory.

ساخت اپلیکیشن، ثبت routerها، CORS و رویدادهای چرخه‌ی عمر.
در production، تنظیمات ناامن باعث fail-fast می‌شوند (بند 69).
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.routing import Match, Mount

from backend.ai.schemas.types import AIError
from backend.api.errors import (
    REQUEST_ID_HEADER,
    RequestIDMiddleware,
    ai_error_handler,
    install_error_handlers,
)
from backend.api.routers import (
    ai,
    ai_routing,
    alerts,
    analogues,
    analyses,
    archive,
    audit,
    briefings,
    claims,
    classify,
    configuration,
    country_profile,
    dashboard,
    debate,
    decisions,
    dedup,
    dispatch,
    economic,
    evaluation,
    events,
    forecasts,
    geo,
    geopolitics,
    graph,
    health,
    inbox,
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
    retention,
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
from backend.auth.deps import access_guard
from backend.core.config import get_settings
from backend.core.logging import configure_logging, get_logger
from backend.core.security import RateLimitMiddleware, SecurityHeadersMiddleware

logger = get_logger(__name__)


class _StaticUIMount(Mount):
    """Mount استاتیک که `/api/*` را هرگز نمی‌بلعد.

    وقتی StaticFiles روی `/` سوار باشد، درخواستی مثل `GET /api/ingest/all` (که
    فقط POST دارد) به‌جای 405 به دنبال فایل می‌رود و 404 می‌شود، چون Mount
    «تطابق کامل» دارد و تطابق جزئیِ روش (405) کنار گذاشته می‌شود. با رد کردن
    `/api` از این mount، Starlette همان 404/405 درست را با پاکت خطا می‌دهد.
    """

    def matches(self, scope):  # noqa: ANN001, ANN201
        if scope.get("type") == "http" and (
            scope.get("path") == "/api" or str(scope.get("path", "")).startswith("/api/")
        ):
            return Match.NONE, {}
        return super().matches(scope)


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
    # مرحله ۱ احراز هویت: seed ادمین اولیه از ADMIN_USERNAME/ADMIN_PASSWORD
    # (اگر تنظیم نشده باشند فقط هشدار؛ هیچ رمز پیش‌فرضی ساخته نمی‌شود).
    try:
        from backend.auth.bootstrap import seed_admin_user
        from backend.database.session import get_session_factory as _gsf_auth

        with _gsf_auth()() as _db:
            seed_admin_user(_db)
        from backend.auth.maintenance import cleanup_auth_state

        with _gsf_auth()() as _db:
            removed = cleanup_auth_state(_db)
        if any(removed.values()):
            logger.info("auth cleanup | %s", removed)
    except Exception:  # noqa: BLE001 — بدون DB هم سرور باید بالا بیاید
        logger.warning("admin seed skipped (db or migration unavailable)")
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

    # F-15: اعمال خودکار زنجیره‌ی تطبیقی (پیش‌فرض خاموش؛ فقط با آمار ثبت‌شده)
    if settings.adaptive_routing_enabled:
        try:
            from backend.ai.adaptive_bootstrap import apply_adaptive_routes, parse_tasks
            from backend.database.session import get_session_factory as _gsf_routes

            with _gsf_routes()() as _db:
                applied = apply_adaptive_routes(_db, parse_tasks(settings.adaptive_routing_tasks))
            logger.info("adaptive routing applied | %s", applied)
        except Exception:  # noqa: BLE001 — AI routing must not block startup
            logger.warning("adaptive routing bootstrap skipped (db unavailable)")
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
        # UI باید request_id و شمارش معکوس ۴۲۹ را از پاسخ بخواند
        expose_headers=[REQUEST_ID_HEADER, "Retry-After"],
    )
    # بیرونی‌ترین لایه: هر پاسخ (حتی 429/500) شناسه‌ی درخواست داشته باشد
    app.add_middleware(RequestIDMiddleware)

    # قرارداد یکنواخت خطا (پاکت error + detail قدیمی + X-Request-ID)
    install_error_handlers(app)
    # خطاهای ساختاریافته‌ی AI → وضعیت HTTP معنادار
    app.add_exception_handler(AIError, ai_error_handler)

    # /health بدون احراز هویت (برای probe)، ورود/خروج هم عمومی است (خودش ورود است)
    app.include_router(health.router)
    app.include_router(auth_router.router)
    # نشست کوکی (UI) یا X-API-Key (n8n/اسکریپت‌ها) — مرحله ۱ احراز هویت؛
    # مرحله ۲: نقش بر اساس متد/مسیر (docs/ROLE_MATRIX.md)
    protected = [Depends(access_guard)]
    app.include_router(jobs.router, dependencies=protected)
    app.include_router(ai.router, dependencies=protected)
    app.include_router(ai_routing.router, dependencies=protected)
    app.include_router(alerts.router, dependencies=protected)
    app.include_router(audit.router, dependencies=protected)
    app.include_router(briefings.router, dependencies=protected)
    app.include_router(sources.router, dependencies=protected)
    app.include_router(configuration.router, dependencies=protected)
    app.include_router(ingestion.router, dependencies=protected)
    app.include_router(dedup.router, dependencies=protected)
    app.include_router(classify.router, dependencies=protected)
    app.include_router(debate.router, dependencies=protected)
    app.include_router(events.router, dependencies=protected)
    app.include_router(geo.router, dependencies=protected)
    app.include_router(claims.router, dependencies=protected)
    app.include_router(independence.router, dependencies=protected)
    app.include_router(graph.router, dependencies=protected)
    app.include_router(economic.router, dependencies=protected)
    app.include_router(markets.router, dependencies=protected)
    app.include_router(worldstate.router, dependencies=protected)
    app.include_router(memory.router, dependencies=protected)
    app.include_router(analogues.router, dependencies=protected)
    app.include_router(archive.router, dependencies=protected)
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
    app.include_router(inbox.router, dependencies=protected)
    app.include_router(analyses.router, dependencies=protected)
    app.include_router(dashboard.router, dependencies=protected)
    app.include_router(research.router, dependencies=protected)
    app.include_router(retention.router, dependencies=protected)
    app.include_router(risk.router, dependencies=protected)
    app.include_router(decisions.router, dependencies=protected)
    app.include_router(learning.router, dependencies=protected)
    app.include_router(iran.router, dependencies=protected)
    app.include_router(country_profile.router, dependencies=protected)

    # Serve the single-file UI at "/" (registered after all API routes so it cannot shadow them).
    _static_dir = Path(__file__).resolve().parent / "static"
    if _static_dir.is_dir():
        app.router.routes.append(
            _StaticUIMount(
                "/", app=StaticFiles(directory=str(_static_dir), html=True), name="static-ui"
            )
        )
    return app


app = create_app()
