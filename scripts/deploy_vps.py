"""VPS deployment automation (Phase 48).

- بدون سرور واقعی، فقط dry-run قابل اجراست (استقرار زنده BLOCKED).
- اصل امنیتی: `.env` هرگز منتقل نمی‌شود؛ secretها روی سرور ساخته می‌شوند.
- همه‌ی فرمان‌ها به‌صورت داده ساخته می‌شوند (قابل تست) و بعد اجرا.

اجرا:
    python -m scripts.deploy_vps --host vps.example.com --user root
    python -m scripts.deploy_vps --host <ip> --user <u> --key ~/.ssh/id_rsa --live
"""
from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

REQUIRED_LOCAL_FILES = [
    "docker-compose.yml",
    "docker-compose.prod.yml",
    "docker/backend.Dockerfile",
    "docker/frontend.prod.Dockerfile",
    "docker/nginx-spa.conf",
    ".env.example",
]

REMOTE_DIR = "/opt/globalintelligence"


@dataclass
class DeployPlan:
    host: str
    user: str
    key: str | None
    remote_dir: str = REMOTE_DIR
    steps: list[list[str]] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "host": self.host,
            "user": self.user,
            "remote_dir": self.remote_dir,
            "n_steps": len(self.steps),
        }


def ssh_base(host: str, user: str, key: str | None) -> list[str]:
    """پایه‌ی ssh (BatchMode تا رمز تعاملی گیر نکند)."""
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new"]
    if key:
        cmd += ["-i", key]
    cmd.append(f"{user}@{host}")
    return cmd


def check_local_files(root: Path) -> list[str]:
    """فایل‌های لازم برای استقرار؛ خروجی = موارد گمشده."""
    return [f for f in REQUIRED_LOCAL_FILES if not (root / f).exists()]


def build_steps(host: str, user: str, key: str | None) -> list[list[str]]:
    """فرمان‌های استقرار به ترتیب (اجرا نمی‌شوند؛ فقط داده)."""
    ssh = ssh_base(host, user, key)
    remote = REMOTE_DIR
    return [
        # 1) پیش‌نیاز داکر روی سرور
        ssh + ["docker --version && docker compose version"],
        # 2) پوشه‌ی مقصد (بدون .env — روی سرور ساخته می‌شود)
        ssh + [f"mkdir -p {remote}"],
        # 3) انتقال فایل‌ها (صریحاً بدون .env؛ نگاه کن به check_no_env)
        ["scp", "-r"] + (["-i", key] if key else []) + [
            "docker-compose.yml",
            "docker-compose.prod.yml",
            "docker",
            "db",
            "backend/requirements.txt",
            "alembic.ini",
            f"{user}@{host}:{remote}/",
        ],
        # 4) بیلد و بالا آوردن production
        ssh + [f"cd {remote} && docker compose -f docker-compose.yml "
               "-f docker-compose.prod.yml up -d --build"],
        # 5) سلامت
        ssh + ["curl -sf http://localhost:8000/health/db"],
    ]


def check_no_env(paths: list[str]) -> list[str]:
    """تخلف‌ها: هر مسیر شامل .env واقعی (نه .env.example)."""
    bad = []
    for p in paths:
        name = Path(p).name
        if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            bad.append(p)
    return bad


def run_plan(plan: DeployPlan, dry_run: bool = True) -> int:
    for i, cmd in enumerate(plan.steps, start=1):
        print(f"[step {i}] {' '.join(cmd)}")
        if dry_run:
            continue
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            print(f"FAILED step {i}: {proc.stderr[-500:]}")
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy to VPS")
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", default="root")
    parser.add_argument("--key", default=None)
    parser.add_argument(
        "--live",
        action="store_true",
        help="اجرای واقعی روی سرور (بدون آن فقط dry-run)",
    )
    args = parser.parse_args(argv)

    root = Path(".")
    missing = check_local_files(root)
    if missing:
        print(f"missing local files: {missing}")
        return 1
    plan = DeployPlan(
        host=args.host, user=args.user, key=args.key,
        steps=build_steps(args.host, args.user, args.key),
    )
    transfer_paths = plan.steps[2]
    bad = check_no_env(transfer_paths)
    if bad:
        print(f"REFUSED: .env would be transferred: {bad}")
        return 1
    print(f"plan: {plan.as_dict()}")
    if not args.live:
        print("dry-run only (pass --live to execute)")
    return run_plan(plan, dry_run=not args.live)


if __name__ == "__main__":
    raise SystemExit(main())
