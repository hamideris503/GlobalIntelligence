"""Daily token budget — کنترل مرکزی و اتمیک مصرف AI (Phase 1D).

- سقف فقط وقتی اعمال می‌شود که هم factory سشن ست شده باشد و هم
  `ai_daily_token_budget` پیکربندی شده باشد؛ در غیر این صورت رفتار قبلی.
- هر تلاش واقعی provider پیش از ارسال رزرو می‌شود (single-statement
  شرطی: جمع مصرف روز + تخمین <= سقف، وگرنه ۰ ردیف). رزرو تکراری با همان
  کلید (retry همان attempt) دوباره شمرده نمی‌شود (UNIQUE request_key).
- تسویه با usage واقعی پاسخ؛ نامعلوم/ناموفق محافظه‌کارانه روی رزرو می‌ماند.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database.models.ai_token_ledger import AITokenLedger

_COUNTED = ("reserved", "settled", "unknown", "failed")

_session_factory = None


def set_session_factory(factory) -> None:
    """اتصال ledger به factory سشن (الگوی credentials_store)."""
    global _session_factory
    _session_factory = factory


def reset_session_factory() -> None:
    global _session_factory
    _session_factory = None


def utc_day(day: date | None = None) -> date:
    return day or datetime.now(UTC).date()


def is_enabled() -> bool:
    """کنترل بودجه فقط وقتی فعال است که factory ست و سقف پیکربندی شده باشد."""
    return _session_factory is not None and budget_limit() is not None


def budget_limit() -> int | None:
    """سقف پیکربندی‌شده یا None (کنترل خاموش)."""
    from backend.core.config import get_settings

    value = get_settings().ai_daily_token_budget
    if value is None or value <= 0:
        return None
    return int(value)


# ضریب کالیبراسیون تخمین ورودی (همان مبنای موتور debate،
# domains/debate/engine.py: CALIBRATION_FACTOR) — برای فارسی و سربار
# قالب‌بندی، chars//4 به‌تنهایی کم‌برآورد می‌کند.
INPUT_CALIBRATION = 2.1


def estimate_input_tokens(request) -> int:
    """تخمین تقریبی ورودی: همه‌ی پیام‌ها + اسکیمای JSON ارسالی.

    تقریبی است (نه شمارش دقیق و نه تضمین سقف)؛ با ضریب کالیبره‌شده‌ی
    پروژه محافظه‌کارانه نگه داشته می‌شود.
    """
    import json as _json

    chars = sum(len(m.content or "") for m in (request.messages or []))
    schema = getattr(request, "json_schema", None)
    if schema:
        try:
            chars += len(_json.dumps(schema, ensure_ascii=False, default=str))
        except Exception:  # noqa: BLE001
            pass
    return max(0, int(chars // 4 * INPUT_CALIBRATION))


def _debate_agent_tasks() -> frozenset:
    """نام taskهای واقعی عامل‌های مناظره (منبع: domains.debate.agents)."""
    from domains.debate.agents import AGENTS, QUANT_AGENT

    return frozenset([f"debate_{a}" for a in (*AGENTS, QUANT_AGENT)])


def _positive_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and int(value) > 0:
        return int(value)
    return None


def resolve_output_cap(request) -> int | None:
    """سقف مؤثر خروجی: درخواست، سپس نقشه‌ی per-task، وگرنه None.

    تطبیق دقیق نام task همیشه مقدم است؛ عامل‌های مناظره‌ی واقعی به سقف
    مشترک debate_agent می‌رسند (نه prefix-matching عمومی)؛ debate_report
    کلید اختصاصی خودش را دارد. همان مقادیری که providerها enforce می‌کنند.
    """
    from backend.core.config import get_settings

    direct = _positive_int(getattr(request, "max_tokens", None))
    if direct is not None:
        return direct
    task_map = get_settings().ai_task_max_tokens or {}
    task = getattr(request, "task", None)
    if not isinstance(task, str):
        return None
    cap = _positive_int(task_map.get(task))
    if cap is not None:
        return cap
    if task in _debate_agent_tasks():
        return _positive_int(task_map.get("debate_agent"))
    return None


def spent_today(db: Session, day: date) -> int:
    """جمع مصرف شمارش‌شده‌ی روز (رزرو/تسویه‌شده/نامعلوم/ناموفق)."""
    total = db.execute(
        select(func.coalesce(
            func.sum(func.coalesce(AITokenLedger.actual_tokens,
                                   AITokenLedger.reserved_tokens)), 0))
        .where(AITokenLedger.day == day,
               AITokenLedger.status.in_(_COUNTED))
    ).scalar()
    return int(total or 0)


def _day_lock_key(day: date) -> int:
    """کلید پایدار قفل روزانه (sha256، نه hash() پایتون؛ در همه processها یکسان)."""
    import hashlib

    digest = hashlib.sha256(f"ai-budget-day:{day.isoformat()}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def _acquire_day_lock(db: Session, day: date) -> None:
    """قفل transaction-level مشترک bucket روز (فقط PostgreSQL).

    تا پایان transaction نگه داشته می‌شود و با commit/rollback آزاد می‌شود.
    """
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"),
                   {"k": _day_lock_key(day)})
def _own_session(db: Session | None) -> tuple[Session | None, bool]:
    if db is not None:
        return db, False
    if _session_factory is None:
        return None, False
    return _session_factory(), True


def reserve(*, db: Session | None = None, day: date, task: str | None,
            provider: str | None, model: str | None, request_key: str,
            estimate: int, budget: int,
            input_est: int | None = None,
            output_cap: int | None = None) -> bool:
    """رزرو اتمیک یک attempt؛ True = فضا بود و ثبت شد (یا از قبل بود).

    ترتیب ثابت در یک transaction: قفل روز -> بررسی تکراری -> خواندن
    مصرف (statement جدا، پس از قفل) -> درج با RETURNING -> commit.
    """
    db, own = _own_session(db)
    if db is None:
        return True  # بدون سشن، کنترلی ممکن نیست (رفتار قبلی)
    try:
        _acquire_day_lock(db, day)
        dup = db.execute(
            select(AITokenLedger.id)
            .where(AITokenLedger.request_key == request_key)
        ).first()
        if dup is not None:
            db.commit()
            return True
        if spent_today(db, day) + max(0, int(estimate)) > int(budget):
            db.commit()
            return False
        row = db.execute(
            insert(AITokenLedger).values(
                id=uuid.uuid4(), day=day, task=task, provider=provider,
                model=model, request_key=request_key,
                reserved_tokens=max(0, int(estimate)), status="reserved",
                estimated_input_tokens=input_est, output_cap_tokens=output_cap)
            .returning(AITokenLedger.id)
        ).fetchone()
        db.commit()
        return row is not None
    except IntegrityError:
        db.rollback()
        existing = db.execute(
            select(AITokenLedger.id)
            .where(AITokenLedger.request_key == request_key)
        ).first()
        try:
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
        return existing is not None
    finally:
        if own:
            db.close()


def settle(request_key: str, *, actual: int | None, status: str,
           db: Session | None = None) -> None:
    """تسویه یک رزرو با usage واقعی (None = نامعلوم می‌ماند)."""
    own = False
    if db is None:
        if _session_factory is None:
            return
        db = _session_factory()
        own = True
    try:
        row = db.execute(
            select(AITokenLedger)
            .where(AITokenLedger.request_key == request_key)
        ).scalars().first()
        if row is None:
            return
        if actual is not None:
            row.actual_tokens = max(0, int(actual))
        row.status = status
        db.commit()
    finally:
        if own:
            db.close()


def release(request_key: str, db: Session | None = None) -> None:
    """آزادسازی رزروِ اثبات‌شده‌بی‌مصرف (پیش از ارسال واقعی)."""
    own = False
    if db is None:
        if _session_factory is None:
            return
        db = _session_factory()
        own = True
    try:
        row = db.execute(
            select(AITokenLedger)
            .where(AITokenLedger.request_key == request_key)
        ).scalars().first()
        if row is not None and row.status == "reserved":
            row.status = "released"
            db.commit()
    finally:
        if own:
            db.close()


def get_daily_usage(db: Session, day: date) -> dict:
    """گزارش روز به تفکیک task (رزرو/واقعی جدا)."""
    rows = db.execute(
        select(
            AITokenLedger.task,
            func.count(),
            func.coalesce(func.sum(AITokenLedger.reserved_tokens), 0),
            func.coalesce(func.sum(AITokenLedger.actual_tokens), 0),
        )
        .where(AITokenLedger.day == day,
               AITokenLedger.status.in_(_COUNTED))
        .group_by(AITokenLedger.task)
    ).all()
    by_task = {t or "unknown": {"attempts": n, "reserved": int(r), "actual": int(a)}
               for t, n, r, a in rows}
    return {"day": day.isoformat(), "by_task": by_task,
            "reserved_total": sum(v["reserved"] for v in by_task.values()),
            "actual_total": sum(v["actual"] for v in by_task.values())}
