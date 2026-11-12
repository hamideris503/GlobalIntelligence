"""
GlobalIntelligence — Legacy UI Backup Integrity Check

هش فایل‌های UI که در STEP 6A.13 حذف شدند را با مقادیر مرجع ثبت‌شده در
`docs/qa/STEP_6A_43_LEGACY_UI_RETIREMENT_FORMALIZATION.md` مقایسه می‌کند تا
مسیر بازیابی (rollback) همیشه قابل اعتماد بماند.

اجرا:
    python scripts/check_legacy_ui_backup.py
    python scripts/check_legacy_ui_backup.py --path "D:/backup/legacy_ui/static"
    python scripts/check_legacy_ui_backup.py --live-only   # گام CI: فقط عدم بازگشت فایل‌ها

خروجی: کد 0 اگر حداقل یک نسخهٔ کامل و مطابق پیدا شود، وگرنه 1.
هیچ فایلی تغییر نمی‌کند، هیچ مقدار حساسی خوانده/چاپ نمی‌شود و فقط stdlib لازم است.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys

# کنسول ویندوز ممکن است فارسی را نتواند چاپ کند.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

# (اندازهٔ بایت، SHA-256) — منبع: STEP 6A.13 (حذف) + STEP 6A.43 (تأیید)
REFERENCE: dict[str, tuple[int, str]] = {
    "ui-data.js": (
        87_841,
        "e8527e959e44f9057f8322b7ab4776fbb1a8c221becc36e9aa1fc08343a05951",
    ),
    "ui-data.css": (
        5_304,
        "3cb066203bf7b82232ef4298c7175459015ebe3448cb3a9501f4c7c9e832189f",
    ),
}

_TEMP = os.environ.get("TEMP") or os.environ.get("TMP")
DEFAULT_ROOTS: tuple[str, ...] = (
    os.path.join("backups", "legacy_ui_20261112", "backend", "static"),
    *(
        (os.path.join(_TEMP, "opencode", "legacy_ui_backup", "backend", "static"),)
        if _TEMP
        else ()
    ),
)

# اگر این دو فایل به این مسیر برگردند، وضعیت F03.UX.8 عملاً بازگشایی شده است.
LIVE_DIR = os.path.join("backend", "static")


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_root(root: str) -> tuple[bool, list[str]]:
    """یک پوشهٔ پشتیبان را بررسی می‌کند؛ (کامل و مطابق؟، خطوط گزارش)."""
    lines: list[str] = []
    complete = True
    for name, (expected_size, expected_hash) in REFERENCE.items():
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            lines.append(f"  [!!] {name:<12} موجود نیست")
            complete = False
            continue
        size = os.path.getsize(path)
        actual = sha256_file(path)
        if size == expected_size and actual == expected_hash:
            lines.append(f"  [OK] {name:<12} {size:>7} B · {actual[:12]}…")
        else:
            complete = False
            reason = "اندازه متفاوت" if size != expected_size else "هش متفاوت"
            lines.append(
                f"  [!!] {name:<12} {size:>7} B · {actual[:12]}… ({reason}؛ "
                f"انتظار {expected_size} B · {expected_hash[:12]}…)"
            )
    return complete, lines


def check_live_absent(root: str) -> tuple[bool, str]:
    """تأیید می‌کند فایل‌های legacy به مسیر اجرایی برنگشته‌اند."""
    present = [name for name in REFERENCE if os.path.exists(os.path.join(root, LIVE_DIR, name))]
    if present:
        return False, "برگشتند به " + LIVE_DIR + "/: " + ", ".join(present)
    return True, "حذف‌شده و برنگشته‌اند"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="بررسی سلامت پشتیبان UI قدیمی (STEP 6A.43)")
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        help="پوشهٔ جایگزین برای پشتیبان (قابل تکرار)؛ نسبی نسبت به ریشهٔ پروژه",
    )
    parser.add_argument(
        "--live-only",
        action="store_true",
        help="فقط بررسی کن که فایل‌های legacy به backend/static/ برنگشته باشند (گام CI)",
    )
    args = parser.parse_args(argv)

    root = _repo_root()
    if args.live_only:
        live_ok, live_detail = check_live_absent(root)
        print("=" * 68)
        print("GlobalIntelligence — Legacy UI Guard (F03.UX.8)")
        print("=" * 68)
        print(f"{LIVE_DIR}: {'[OK]' if live_ok else '[!!]'} {live_detail}")
        print(
            "توجه: بررسی هش پشتیبان میزبان‌محور است؛ backups/ عمداً در .gitignore است و "
            "در CI در دسترس نیست (کامل را روی میزبان اجرا کنید)."
        )
        return 0 if live_ok else 1
    roots = [os.path.join(root, p) if not os.path.isabs(p) else p for p in args.path] or [
        os.path.join(root, p) if not os.path.isabs(p) else p for p in DEFAULT_ROOTS
    ]

    print("=" * 68)
    print("GlobalIntelligence — Legacy UI Backup Integrity Check (STEP 6A.43)")
    print("=" * 68)

    verified: list[str] = []
    for candidate in roots:
        print(f"\nپوشه: {candidate}")
        if not os.path.isdir(candidate):
            print("  [--] این پوشه وجود ندارد")
            continue
        ok, lines = check_root(candidate)
        print("\n".join(lines))
        if ok:
            verified.append(candidate)

    live_ok, live_detail = check_live_absent(root)
    print(f"\nمسیر اجرایی ({LIVE_DIR}): {'[OK]' if live_ok else '[!!]'} {live_detail}")
    print("=" * 68)

    if not verified:
        print("نتیجه: هیچ نسخهٔ کامل و مطابق هش پیدا نشد — پشتیبان تأیید نشده است.")
        return 1

    print(f"نتیجه: {len(verified)} نسخهٔ تأییدشده پیدا شد:")
    for path in verified:
        print(f"  - {path}")
    if not live_ok:
        print("هشدار: فایل‌های legacy دوباره در مسیر اجرایی ظاهر شده‌اند (UX.8 بازگشایی شده).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
