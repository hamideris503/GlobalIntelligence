"""
GlobalIntelligence — Environment Check (Phase 1)

بررسی می‌کند که ابزارهای لازم برای توسعه نصب و قابل دسترس هستند.
اجرا:
    python scripts/check_env.py

خروجی: گزارش وضعیت با کد خروجی 0 (همه حیاتی‌ها OK) یا 1 (کمبود حیاتی).
بدون وابستگی خارجی کار می‌کند (فقط stdlib).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass

# کنسول ویندوز ممکن است cp1256 باشد و فارسی را نتواند چاپ کند.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

MIN_PYTHON = (3, 11)
MIN_NODE_MAJOR = 18


@dataclass
class Result:
    name: str
    ok: bool
    detail: str
    required: bool = True


def _resolve(exe: str) -> str | None:
    """مسیر اجرایی را با در نظر گرفتن پسوندهای ویندوز (cmd/bat) پیدا می‌کند."""
    found = shutil.which(exe)
    if found:
        return found
    for suffix in (".cmd", ".bat", ".exe"):
        found = shutil.which(exe + suffix)
        if found:
            return found
    return None


def _run(cmd: list[str]) -> str | None:
    try:
        out = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=20,
            shell=False,
            encoding="utf-8",
            errors="replace",
        )
        text = (out.stdout or out.stderr).strip()
        return text.splitlines()[0] if text else ""
    except Exception:
        return None


def _run_named(name: str, args: list[str]) -> str | None:
    """اجرای یک ابزار با نام؛ روی ویندوز فایل‌های .cmd را از طریق cmd اجرا می‌کند."""
    exe = _resolve(name)
    if not exe:
        return None
    low = exe.lower()
    if low.endswith((".cmd", ".bat")):
        return _run(["cmd", "/c", exe, *args])
    return _run([exe, *args])


def check_git() -> Result:
    exe = shutil.which("git")
    if not exe:
        return Result("Git", False, "پیدا نشد", required=True)
    return Result("Git", True, _run_named("git", ["--version"]) or "installed")


def check_python() -> Result:
    v = sys.version_info
    ok = (v.major, v.minor) >= MIN_PYTHON
    return Result(
        "Python",
        ok,
        f"{v.major}.{v.minor}.{v.micro} (حداقل لازم: {MIN_PYTHON[0]}.{MIN_PYTHON[1]})",
        required=True,
    )


def check_pip() -> Result:
    txt = _run([sys.executable, "-m", "pip", "--version"])
    return Result("pip", txt is not None, txt or "پیدا نشد", required=True)


def check_node() -> Result:
    exe = _resolve("node")
    if not exe:
        return Result("Node.js", False, "پیدا نشد", required=True)
    raw = _run_named("node", ["--version"]) or ""
    try:
        major = int(raw.lstrip("v").split(".")[0])
        ok = major >= MIN_NODE_MAJOR
    except Exception:
        major, ok = -1, False
    return Result("Node.js", ok, f"{raw} (حداقل لازم: v{MIN_NODE_MAJOR})", required=True)


def check_npm() -> Result:
    txt = _run_named("npm", ["--version"])
    return Result("npm", txt is not None, txt or "پیدا نشد", required=True)


def check_docker_cli() -> Result:
    txt = _run_named("docker", ["--version"])
    return Result("Docker CLI", txt is not None, txt or "پیدا نشد", required=True)


def check_docker_compose() -> Result:
    txt = _run_named("docker", ["compose", "version"])
    return Result("Docker Compose", txt is not None, txt or "پیدا نشد", required=True)


def check_docker_daemon() -> Result:
    txt = _run_named("docker", ["info", "--format", "{{.ServerVersion}}"])
    ok = bool(txt) and "error" not in txt.lower()
    return Result(
        "Docker Daemon",
        ok,
        (txt if ok else "در حال اجرا نیست — Docker Desktop را شروع کنید"),
        required=False,
    )


def main() -> int:
    checks = [
        check_git(),
        check_python(),
        check_pip(),
        check_node(),
        check_npm(),
        check_docker_cli(),
        check_docker_compose(),
        check_docker_daemon(),
    ]

    print("=" * 60)
    print("GlobalIntelligence — Environment Check")
    print("=" * 60)
    critical_fail = False
    for r in checks:
        mark = "OK " if r.ok else "!! "
        tag = "" if r.required else " (غیرحیاتی)"
        print(f"[{mark}] {r.name:<16}{tag}: {r.detail}")
        if r.required and not r.ok:
            critical_fail = True
    print("=" * 60)

    if critical_fail:
        print("نتیجه: کمبود حیاتی وجود دارد. موارد بالا را نصب کنید.")
        return 1

    if not checks[-1].ok:
        print("نتیجه: همه ابزارهای حیاتی OK. (Docker Daemon هنوز اجرا نشده)")
    else:
        print("نتیجه: همه ابزارها OK. محیط آماده است.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
