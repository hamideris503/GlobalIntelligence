"""Staging/prod smoke checks (Phase 47).

بررسی‌های فقط‌خواندنی سلامت استقرار: health، احراز هویت، endpointهای کلیدی.
خروجی: گزارش JSON + کد خروج (۰ یعنی همه سبز).

اجرا:
    python -m scripts.smoke_check --base http://localhost:8001 --api-key <key>
"""
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""

    def as_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


@dataclass
class SmokeReport:
    passed: int = 0
    failed: int = 0
    checks: list[CheckResult] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "failed": self.failed,
            "checks": [c.as_dict() for c in self.checks],
        }

    @property
    def ok(self) -> bool:
        return self.failed == 0


PUBLIC_CHECKS: list[tuple[str, str]] = [
    ("health", "/health"),
    ("health_db", "/health/db"),
]

PROTECTED_CHECKS: list[tuple[str, str]] = [
    ("sources", "/api/sources?limit=1"),
    ("economic_indicators", "/api/economic/indicators"),
    ("market_symbols", "/api/markets/symbols"),
    ("world_state_history", "/api/world-state/history?limit=1"),
    ("self_eval_history", "/api/self-eval/history?limit=1"),
    ("briefings", "/api/briefings?limit=1"),
]


def _get(base: str, path: str, api_key: str | None, timeout: int = 15) -> tuple[int, str]:
    """(status, body)؛ خطای اتصال → (0, متن خطا)."""
    req = urllib.request.Request(base.rstrip("/") + path)
    if api_key:
        req.add_header("X-API-Key", api_key)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")[:500]
    except urllib.error.HTTPError as exc:
        return exc.code, (exc.read().decode("utf-8", "replace")[:200] if exc.fp else "")
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}"


def run_smoke(base: str, api_key: str | None = None) -> SmokeReport:
    """اجرای همه‌ی چک‌ها و ساخت گزارش."""
    report = SmokeReport()

    def record(name: str, ok: bool, detail: str = "") -> None:
        report.checks.append(CheckResult(name, ok, detail))
        if ok:
            report.passed += 1
        else:
            report.failed += 1

    for name, path in PUBLIC_CHECKS:
        status, body = _get(base, path, None)
        record(name, status == 200, f"HTTP {status} {body[:80]}")

    # بدون کلید باید 401 باشد (احراز هویت فعال است)
    status, _ = _get(base, "/api/sources?limit=1", None)
    record("auth_enforced", status in (401, 403), f"HTTP {status}")

    if api_key:
        for name, path in PROTECTED_CHECKS:
            status, body = _get(base, path, api_key)
            record(name, status == 200, f"HTTP {status} {body[:80]}")
    else:
        record("protected_checks", False, "no API key provided; skipped")

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Staging smoke checks")
    parser.add_argument("--base", default="http://localhost:8001")
    parser.add_argument("--api-key", default=None, dest="api_key")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_smoke(args.base, args.api_key)
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
