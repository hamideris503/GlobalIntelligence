"""نگهبان هم‌خوانیِ ماتریس نقش با کد (WP-04.1).

`docs/ROLE_MATRIX.md` ادعا می‌کند از روی جدول واقعی مسیرها تولید شده است. این
تست همان ادعا را اجرایی می‌کند: هر مسیر API که در اپ ثبت شده باید در سند
با همان نقش باشد، و هر ردیف سند باید یک مسیر واقعی باشد. اگر endpoint جدیدی
اضافه شود و نقشش در سند نیاید، این تست می‌شکند تا سیاست به‌صورت ناخواسته
تغییر نکند.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.auth.deps import required_role
from backend.main import app

ROLE_DOC = Path(__file__).resolve().parents[1] / "docs" / "ROLE_MATRIX.md"
ROW = re.compile(r"^\|\s*(GET|POST|PUT|PATCH|DELETE)\s*\|\s*`([^`]+)`\s*\|\s*(viewer|analyst|admin)\s*\|")

# مسیرهایی که آگاهانه خارج از ماتریس‌اند: probe سلامت و مسیرهای عمومی Auth.
EXCLUDED_PREFIXES = ("/api/auth/", "/health")


def _documented() -> set[tuple[str, str, str]]:
    rows: set[tuple[str, str, str]] = set()
    for line in ROLE_DOC.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line.strip())
        if m:
            rows.add((m.group(1), m.group(2).strip(), m.group(3)))
    return rows


def _actual() -> set[tuple[str, str, str]]:
    rows: set[tuple[str, str, str]] = set()
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", "")
        if not methods or not path.startswith("/api/"):
            continue
        if path.startswith(EXCLUDED_PREFIXES):
            continue
        for method in sorted(methods):
            if method in ("HEAD", "OPTIONS"):
                continue
            rows.add((method, path, required_role(method, path)))
    return rows


def test_permission_doc_matches_code() -> None:
    documented = _documented()
    actual = _actual()
    missing = sorted(actual - documented)
    stale = sorted(documented - actual)
    assert not missing, (
        "این endpointها در docs/ROLE_MATRIX.md نیستند: "
        + ", ".join(f"{m} {p} -> {r}" for m, p, r in missing)
    )
    assert not stale, (
        "این ردیف‌های سند مسیر/نقش واقعی ندارند: "
        + ", ".join(f"{m} {p} -> {r}" for m, p, r in stale)
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/settings/providers"),
        ("POST", "/api/settings/providers/{provider_id}/key"),
        ("POST", "/api/settings/models/{model_id}/verify"),
        ("PUT", "/api/settings/app"),
        ("POST", "/api/alerts/test-deliver/{channel}"),
        ("POST", "/api/dispatch/recover-screening"),
        ("POST", "/api/archive/restore"),
    ],
)
def test_sensitive_routes_require_admin(method: str, path: str) -> None:
    assert required_role(method, path) == "admin"


def test_no_write_route_is_reachable_by_viewer() -> None:
    viewer_writes = [
        (m, p) for m, p, r in _actual() if r == "viewer" and m not in ("GET", "HEAD", "OPTIONS")
    ]
    assert viewer_writes == [], f"مسیرهای نویسنده با نقش viewer: {viewer_writes}"


def test_operational_reads_stay_admin_only() -> None:
    for path in (
        "/api/settings/providers",
        "/api/settings/app",
        "/api/archive/storage",
        "/api/audit/records",
        "/api/ops/status",
        "/api/local-runtimes/status",
    ):
        assert required_role("GET", path) == "admin", path
