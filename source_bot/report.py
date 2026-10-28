"""گزارش روزانهٔ Source Bot به تفکیک منبع — فقط خواندن، بدون جدول جدید.

منبع حقیقت: `JobRun(job_name="ingest").payload["result"]` که همان
`BotMetrics.as_dict()` است و شامل `by_source` می‌شود. هیچ عددی حدس زده نمی‌شود:
شاخصی که با سازوکار فعلی اندازه‌گیری نمی‌شود در `unavailable_fields` صریحاً
ناموجود اعلام می‌شود و اجرای قدیمی بدون دادهٔ تفکیکی به‌عنوان شکاف تاریخی
شمرده می‌شود، نه صفر جعلی.
"""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models.job import JobRun

TIMEZONE = "UTC"
JOB_NAME = "ingest"
LEVELS = ("P0", "P1", "P2", "P3", "P4")

# شاخص‌هایی که با سازوکار فعلی اندازه‌گیری نمی‌شوند → به‌صورت صفر گزارش نمی‌شوند.
UNAVAILABLE_FIELDS: dict[str, str] = {
    "ai_cost_usd": "هیچ provider واقعی نرخ/هزینه گزارش نمی‌کند (فقط mock مقدار 0.0 می‌دهد)؛ "
                   "هزینه فقط وقتی گزارش می‌شود که خود پاسخ provider مقدار cost داشته باشد",
    "ai_http_attempts": "retry/fallback داخل AI Gateway شفاف نیست؛ فقط فراخوانی‌های سطح "
                        "Source Bot (یک پاسخ نهایی) شمرده می‌شوند",
}

# محدودیت‌های اندازه‌گیری که در خود گزارش باید همراه اعداد دیده شوند.
MEASUREMENT_CAVEATS = (
    "توکن‌ها فقط از usage گزارش‌شدهٔ provider جمع می‌شوند؛ پاسخ بدون usage کامل در "
    "ai.usage_missing شمرده می‌شود و در اعداد وارد نمی‌شود.",
    "mock مصرف واقعی ندارد و فقط در ai.mock شمرده می‌شود؛ Cloudflare usage را با تخمین "
    "chars/4 می‌دهد (backend/ai/providers/cloudflare.py) و از ai.providers قابل تشخیص است.",
    "هر فراخوانی Source Bot یک‌بار شمرده می‌شود؛ retry داخلی Gateway پاسخ جداگانه‌ای با "
    "usage مستقل برنمی‌گرداند، پس دوباره‌شماری نمی‌شود و تلاش‌های ناموفق HTTP هم دیده نمی‌شوند.",
)

NOTES = (
    "شمارنده‌ها فقط رویداد درون‌منبعی (درون batch و همان منبع در DB) را می‌شمارند؛ "
    "dedup پس از ingest (duplicate_cluster) عمداً در این اعداد نیست تا دوباره‌شماری نشود.",
    "هر رویداد یک بار شمرده می‌شود: refused/duplicate در مسیر آیتم، و retry از "
    "fetch_attempts مشتق می‌شود (attempts-1).",
    "اجرای ناموفقِ بدون نتیجه در `history_gap` گزارش می‌شود و در آمار هیچ منبعی وارد نمی‌شود.",
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _int(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _payload(run: JobRun) -> dict:
    try:
        data = json.loads(run.payload or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _run_time(run: JobRun) -> datetime | None:
    for value in (run.finished_at, run.started_at):
        if value is None:
            continue
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return None


def job_records(db: Session, *, start: datetime | None = None, end: datetime | None = None,
                job_name: str = JOB_NAME) -> list[dict]:
    """اجراهای ثبت‌شدهٔ Job را به رکوردهای خالص (at/status/message/result) تبدیل می‌کند."""
    stmt = select(JobRun).where(JobRun.job_name == job_name).order_by(JobRun.started_at)
    out: list[dict] = []
    for run in db.execute(stmt).scalars().all():
        at = _run_time(run)
        if at is None or (start is not None and at < start) or (end is not None and at >= end):
            continue
        payload = _payload(run)
        result = payload.get("result")
        out.append({
            "at": at,
            "status": run.status or "",
            "message": run.message,
            "result": result if isinstance(result, dict) else None,
        })
    return out


def range_bounds(*, day: str | None = None, days: int | None = None,
                 now: datetime | None = None) -> tuple[datetime | None, datetime | None, str | None]:
    """بازهٔ UTC: یک روز کامل شمسی(ISO) یا N روز منتهی به امروز؛ هیچ‌کدام = کل تاریخچه."""
    if day:
        parsed = date.fromisoformat(day)
        start = datetime.combine(parsed, time.min, tzinfo=UTC)
        return start, start + timedelta(days=1), parsed.isoformat()
    if days is not None:
        if days < 1:
            raise ValueError("days must be >= 1")
        today = (now or datetime.now(UTC)).date()
        end = datetime.combine(today, time.min, tzinfo=UTC) + timedelta(days=1)
        return end - timedelta(days=days), end, None
    return None, None, None


def _empty_source(name: str) -> dict:
    return {
        "name": name,
        "runs": 0,
        "ok_runs": 0,
        "failed_runs": 0,
        "no_fetch_runs": 0,
        "partial_runs": 0,
        "fetch_attempts": 0,
        "retries": 0,
        "fetched": 0,
        "items_skipped_limit": 0,
        "stored": 0,
        "duplicates": 0,
        "rejected_keyless": 0,
        "by_priority": dict.fromkeys(LEVELS, 0),
        "pending": 0,
        "ai_used": 0,
        "ai_fallback": 0,
        "duration_ms_total": 0,
        "duration_ms_runs": 0,
        "duration_ms_avg": None,
        "last_run_at": None,
        "last_success_at": None,
        "errors": [],
        "ai": {
            "status": "not_instrumented",
            "runs_instrumented": 0,
            "legacy_runs": 0,
            "requests": 0,
            "ok": 0,
            "failed": 0,
            "mock": 0,
            "providers": {},
            "usage_events": 0,
            "usage_missing": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "tokens_total": 0,
            "cost_usd": None,
            "cost_events": 0,
        },
    }


def _finalize_ai(ai: dict, cost: float | None) -> None:
    """وضعیت مصرف یک منبع: available / partial / missing / not_instrumented."""
    if ai["runs_instrumented"] == 0:
        ai.update({
            "status": "not_instrumented", "requests": None, "ok": None, "failed": None,
            "mock": None, "providers": None, "usage_events": None, "usage_missing": None,
            "tokens_in": None, "tokens_out": None, "tokens_total": None,
            "cost_events": None, "cost_usd": None,
        })
        return
    if ai["requests"] and ai["mock"] == ai["requests"]:
        ai["status"] = "mock_only"  # همهٔ تماس‌ها mock بودند → مصرف واقعی وجود ندارد
        ai["tokens_in"] = ai["tokens_out"] = ai["tokens_total"] = None
    elif ai["requests"] and ai["usage_events"] == 0:
        ai["status"] = "missing"  # فراخوانی داشتیم ولی هیچ usage کاملی نرسید
        ai["tokens_in"] = ai["tokens_out"] = ai["tokens_total"] = None
    elif ai["usage_missing"]:
        ai["status"] = "partial"
    else:
        ai["status"] = "available"
    ai["cost_usd"] = round(cost, 6) if ai["cost_events"] and cost is not None else None


def _ai_totals(rows: list[dict]) -> dict:
    """جمع مصرف AI در بازه — فقط روی منابع ابزاردار؛ ناموجود هرگز صفر نمی‌شود."""
    totals: dict = {
        "status": "not_instrumented", "instrumented_sources": 0,
        "requests": 0, "ok": 0, "failed": 0, "mock": 0,
        "usage_events": 0, "usage_missing": 0,
        "tokens_in": 0, "tokens_out": 0, "tokens_total": 0,
        "cost_usd": None, "cost_events": 0, "providers": {},
    }
    tokens_known = False
    cost_total = 0.0
    for row in rows:
        ai = row["ai"]
        if ai["status"] == "not_instrumented":
            continue
        totals["instrumented_sources"] += 1
        for key in ("requests", "ok", "failed", "mock",
                    "usage_events", "usage_missing", "cost_events"):
            totals[key] += ai[key]
        if ai["tokens_total"] is not None:
            tokens_known = True
            for key in ("tokens_in", "tokens_out", "tokens_total"):
                totals[key] += ai[key]
        if ai["cost_events"]:
            cost_total += ai["cost_usd"] or 0.0
        for provider, count in (ai["providers"] or {}).items():
            totals["providers"][provider] = totals["providers"].get(provider, 0) + count

    if not totals["instrumented_sources"]:
        for key in ("requests", "ok", "failed", "mock", "usage_events", "usage_missing",
                    "tokens_in", "tokens_out", "tokens_total", "cost_events"):
            totals[key] = None
        totals["providers"] = None
        return totals
    if not tokens_known:
        totals["tokens_in"] = totals["tokens_out"] = totals["tokens_total"] = None
    totals["cost_usd"] = round(cost_total, 6) if totals["cost_events"] else None
    totals["status"] = "partial" if totals["usage_missing"] else "available"
    return totals


def build_daily_report(records: list[dict], *, start: datetime | None = None,
                       end: datetime | None = None, day: str | None = None) -> dict:
    """گزارش تفکیک‌شدهٔ هر منبع از رکوردهای واقعی اجرا (تابع خالص و idempotent)."""
    sources: dict[str, dict] = {}
    runs_total = len(records)
    with_result = 0
    failed_without_result = 0
    without_per_source = 0
    without_ai_usage = 0
    cost_sums: dict[str, float] = {}

    for rec in records:
        at = rec.get("at")
        result = rec.get("result")
        if not isinstance(result, dict):
            failed_without_result += 1
            continue
        with_result += 1
        by_source = result.get("by_source")
        if not isinstance(by_source, dict) or not by_source:
            without_per_source += 1  # اجرای قدیمی‌تر از ثبت تفکیکی — عدد جایگزین نمی‌سازیم
            continue
        failures = result.get("sources_failed")
        failures = failures if isinstance(failures, dict) else {}

        # اجرای قبل از مرحلهٔ ۱۶ دادهٔ مصرف AI ندارد → ناموجود، نه صفر.
        if not any(isinstance(st, dict) and "ai_calls" in st for st in by_source.values()):
            without_ai_usage += 1

        for raw_name, raw_stats in by_source.items():
            name = str(raw_name)
            stats = raw_stats if isinstance(raw_stats, dict) else {}
            row = sources.setdefault(name, _empty_source(name))
            row["runs"] += 1
            ok = stats.get("ok") is True
            failed = name in failures
            row["ok_runs"] += int(ok)
            row["failed_runs"] += int(failed)
            attempts = _int(stats.get("fetch_attempts"))
            row["no_fetch_runs"] += int(attempts == 0)
            row["fetch_attempts"] += attempts
            row["retries"] += max(0, attempts - 1)
            for field in ("fetched", "items_skipped_limit", "stored", "duplicates",
                          "rejected_keyless", "pending", "ai_used", "ai_fallback"):
                row[field] += _int(stats.get(field))
            if rec.get("status") == "partial":  # JobRun ناقص: توقف کنترل‌شده یا شکست بخشی از منابع
                row["partial_runs"] += 1
            levels = stats.get("by_priority")
            if isinstance(levels, dict):
                for level in LEVELS:
                    row["by_priority"][level] += _int(levels.get(level))
            self_ai = row["ai"]
            if "ai_calls" in stats:
                self_ai["runs_instrumented"] += 1
                for target, source_key in (
                    ("requests", "ai_calls"), ("ok", "ai_ok"), ("failed", "ai_failed"),
                    ("mock", "ai_mock"), ("usage_events", "ai_usage_events"),
                    ("usage_missing", "ai_usage_missing"), ("tokens_in", "ai_tokens_in"),
                    ("tokens_out", "ai_tokens_out"), ("tokens_total", "ai_tokens_total"),
                    ("cost_events", "ai_cost_events"),
                ):
                    self_ai[target] += _int(stats.get(source_key))
                used_providers = stats.get("ai_providers")
                if isinstance(used_providers, dict):
                    for provider, count in used_providers.items():
                        key = str(provider)
                        self_ai["providers"][key] = self_ai["providers"].get(key, 0) + _int(count)
                reported_cost = stats.get("ai_cost_usd")
                if isinstance(reported_cost, (int, float)) and not isinstance(reported_cost, bool):
                    cost_sums[name] = round(cost_sums.get(name, 0.0) + float(reported_cost), 6)
            else:
                self_ai["legacy_runs"] += 1
            duration = stats.get("duration_ms")
            if isinstance(duration, int) and not isinstance(duration, bool):
                row["duration_ms_total"] += duration
                row["duration_ms_runs"] += 1
            if isinstance(at, datetime):
                if row["last_run_at"] is None or at > row["last_run_at"]:
                    row["last_run_at"] = at
                if ok and (row["last_success_at"] is None or at > row["last_success_at"]):
                    row["last_success_at"] = at
            message = failures.get(name)
            if message:
                safe = str(message)[:200]  # پیام امن آداپتور؛ متن خام خبر هرگز اینجا نیست
                if safe not in row["errors"]:
                    row["errors"].append(safe)

    rows = []
    for row in sources.values():
        runs = row["duration_ms_runs"]
        row["duration_ms_avg"] = round(row["duration_ms_total"] / runs) if runs else None
        row["last_run_at"] = _iso(row["last_run_at"])
        row["last_success_at"] = _iso(row["last_success_at"])
        _finalize_ai(row["ai"], cost_sums.get(row["name"]))
        rows.append(row)

    rows.sort(key=lambda row: row["name"])
    return {
        "generated_from": "job_runs(job_name=ingest).payload.result.by_source",
        "timezone": TIMEZONE,
        "day": day,
        "from": _iso(start),
        "to": _iso(end),
        "runs": {
            "total": runs_total,
            "with_result": with_result,
            "failed_without_result": failed_without_result,
            "without_per_source": without_per_source,
        },
        "history_gap": {
            "runs_without_per_source": without_per_source,
            "runs_without_result": failed_without_result,
            "runs_without_ai_usage": without_ai_usage,
            "reason": "پیش از ثبت تفکیکی فقط aggregate وجود داشت؛ این اجراها در آمار هر منبع نیامده‌اند.",
        },
        "unavailable_fields": UNAVAILABLE_FIELDS,
        "measurement_caveats": list(MEASUREMENT_CAVEATS),
        "items_skipped_limit": sum(row["items_skipped_limit"] for row in rows),
        "ai_usage": _ai_totals(rows),
        "notes": list(NOTES),
        "sources": rows,
    }
