"""Ingestion jobs — چرخه‌ی عمر `JobRun` برای دریافت چندمنبعی در پس‌زمینه.

اجرا در همان پروسه‌ی اپ (FastAPI BackgroundTasks) است؛ وضعیت پایدار در DB
می‌ماند، claim اتمیک از اجرای دوباره جلوگیری می‌کند و Jobهای نیمه‌کاره در
startup علامت‌گذاری می‌شوند. بدون scheduler و بدون worker توزیع‌شده.
اجرای واقعی همان `source_bot.runner.run_once` است (منطق دریافت تکراری نمی‌سازیم).
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models.job import JobRun
from backend.database.session import get_session_factory
from source_bot.config import BotConfigError
from source_bot.runner import run_once

logger = get_logger(__name__)

JOB_NAME = "ingest"
ACTIVE_STATUSES = ("pending", "running")
INTERRUPTED_MESSAGE = "interrupted: process restarted before completion"


def create_job(db: Session, *, spec: dict) -> JobRun:
    """ثبت Job در وضعیت pending (اجرای هم‌زمان دوم -> RuntimeError)."""
    active = db.execute(
        select(JobRun.id).where(
            JobRun.job_name == JOB_NAME, JobRun.status.in_(ACTIVE_STATUSES)
        )
    ).first()
    if active is not None:
        raise RuntimeError(f"ingest job already active: {active[0]}")
    run = JobRun(
        job_name=JOB_NAME,
        source="api",
        status="pending",
        payload=json.dumps({"spec": spec}, ensure_ascii=False),
        message="accepted",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _payload(run: JobRun) -> dict:
    try:
        data = json.loads(run.payload or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def claim_job(db: Session, job_id: uuid.UUID) -> bool:
    """claim اتمیک pending→running؛ False یعنی قبلاً claim شده (اجرای دوباره ممنوع)."""
    res = db.execute(
        update(JobRun)
        .where(JobRun.id == job_id, JobRun.status == "pending")
        .values(status="running", message="running")
    )
    db.commit()
    db.expire_all()
    return (res.rowcount or 0) == 1


def job_status(*, ok: int, failed: int) -> str:
    """completed | partial | failed — partial فقط وقتی بخشی موفق و بخشی ناموفق بوده."""
    if failed and ok:
        return "partial"
    return "failed" if failed else "completed"


def finish_job(db: Session, job_id: uuid.UUID, *, status: str, result: dict | None = None,
               message: str | None = None, duration_ms: int | None = None) -> None:
    """بستن Job: نتیجه در payload (JSON) و وضعیت/زمان/مدت در ستون‌های موجود."""
    run = db.get(JobRun, job_id)
    if run is None:
        return
    data = _payload(run)
    if result is not None:
        data["result"] = result
    run.payload = json.dumps(data, ensure_ascii=False)
    run.status = status
    run.message = (message or "")[:2000] or None
    run.finished_at = datetime.now(UTC)
    run.duration_ms = duration_ms
    db.commit()


def job_view(run: JobRun) -> dict:
    """نمای امن Job برای API (بدون payload خام؛ فقط spec/result خودمان)."""
    data = _payload(run)
    return {
        "id": str(run.id),
        "job_name": run.job_name,
        "status": run.status,
        "message": run.message,
        "created_at": run.started_at,
        "started_at": data.get("run_started_at"),
        "finished_at": run.finished_at,
        "duration_ms": run.duration_ms,
        "spec": data.get("spec"),
        "result": data.get("result"),
    }


def recover_interrupted_jobs(db: Session) -> int:
    """Jobهای ingestion غیرپایانی را پس از restart به‌عنوان ناموفق/قطع‌شده علامت می‌زند.

    جاری‌بودن واقعی پس از restart قابل تشخیص نیست؛ سیاست صریح: هیچ Job نیمه‌کاره
    در حالت running/pending نمی‌ماند (اجرای درون‌پروسه‌ای بعد از restart وجود ندارد).
    """
    res = db.execute(
        update(JobRun)
        .where(JobRun.job_name == JOB_NAME, JobRun.status.in_(ACTIVE_STATUSES))
        .values(status="failed", message=INTERRUPTED_MESSAGE, finished_at=datetime.now(UTC))
    )
    db.commit()
    n = res.rowcount or 0
    if n:
        logger.warning("interrupted ingest jobs marked failed | n=%s", n)
    return n


async def run_job(job_id: uuid.UUID) -> None:
    """اجرای واقعی Job با session مستقل (BackgroundTask)؛ هرگز استثنا بالا نمی‌رود."""
    db = get_session_factory()()
    try:
        run = db.get(JobRun, job_id)
        if run is None:
            logger.warning("ingest job missing | id=%s", job_id)
            return
        spec = _payload(run).get("spec") or {}
        if not claim_job(db, job_id):
            logger.info("ingest job already claimed | id=%s", job_id)
            return
        started = datetime.now(UTC)
        run = db.get(JobRun, job_id)
        if run is not None:
            data = _payload(run)
            data["run_started_at"] = started.isoformat()
            run.payload = json.dumps(data, ensure_ascii=False)
            db.commit()

        def _fail(message: str) -> None:
            finish_job(db, job_id, status="failed", message=message,
                       duration_ms=int((datetime.now(UTC) - started).total_seconds() * 1000))

        try:
            metrics = await run_once(
                source_name=spec.get("source_name"),
                limit_sources=int(spec.get("limit") or 50),
                max_items_per_source=spec.get("max_items_per_source"),
                db=db,
            )
        except BotConfigError as exc:  # پیکربندی ثابت نامعتبر: اجرا پیش از fetch متوقف شده
            logger.error("ingest job blocked: invalid priority configuration | id=%s | %s",
                         job_id, exc)
            _fail(f"priority configuration invalid: {str(exc)[:200]}")
            return
        except ValueError as exc:  # ورودی نامعتبر (نام منبع) — پیام خودمان، بدون راز
            _fail(f"invalid request: {str(exc)[:120]}")
            return
        except RuntimeError as exc:  # قفل اجرای هم‌زمان ربات پیام ثابت دارد
            _fail("another ingestion run is already active" if "lock" in str(exc)
                  else type(exc).__name__)
            return
        except Exception as exc:  # noqa: BLE001 — پیام امن: فقط نوع خطا؛ جزئیات در لاگ
            logger.exception("ingest job failed | id=%s", job_id)
            _fail(type(exc).__name__)
            return
        data = metrics.as_dict()
        failed = len(data["sources_failed"])
        stopped = bool(data.get("stopped"))
        message = (f"sources_ok={data['sources_ok']} sources_failed={failed} "
                   f"fetched={data['fetched']} stored={data['stored']} "
                   f"duplicates={data['duplicates']}")
        if stopped:  # نتیجهٔ ناقص، هرگز «کامل» جلوه داده نمی‌شود
            message = f"stopped: partial run | {message}"
        finish_job(
            db,
            job_id,
            status="partial" if stopped else job_status(ok=data["sources_ok"], failed=failed),
            result=data,
            message=message,
            duration_ms=int((datetime.now(UTC) - started).total_seconds() * 1000),
        )
    finally:
        db.close()
