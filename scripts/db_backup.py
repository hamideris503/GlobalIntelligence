"""PostgreSQL backup/restore/verify (Phase 45).

- `backup`: pg_dump (custom format) از دیتابیس زنده + manifest (sha256/size) + rotation.
- `restore`: بازگردانی به دیتابیس هدف (پیش‌فرض temp) با محافظ تأیید.
- `verify`: مقایسه‌ی شمارش جدول‌های کلیدی مبدأ/مقصد پس از restore.

اجرا:
    python -m scripts.db_backup backup --dir backups --keep 7
    python -m scripts.db_backup restore --file <f> --target-db gi_restore_test
    python -m scripts.db_backup verify --target-db gi_restore_test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

KEY_TABLES = [
    "sources", "documents", "articles", "events", "claims", "evidence",
    "entities", "entity_relationships", "macro_observations",
    "market_observations", "world_states", "forecasts", "forecast_outcomes",
]


def backup_filename(prefix: str = "gi_backup", now: datetime | None = None) -> str:
    """نام فایل قطعی: gi_backup-YYYYMMDD-HHMMSS.dump."""
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{stamp}.dump"


def select_for_rotation(files: list[str], keep: int) -> list[str]:
    """قدیمی‌ترین‌ها برای حذف (مرتب نام = مرتب زمانی)؛ keep>=1."""
    if keep < 1:
        raise ValueError("keep must be >= 1")
    ordered = sorted(files)
    return ordered[: max(0, len(ordered) - keep)]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(backup_path: Path) -> Path:
    """مانیفست JSON کنار فایل بکاپ (size/sha256/زمان)."""
    manifest = {
        "file": backup_path.name,
        "size_bytes": backup_path.stat().st_size,
        "sha256": sha256_file(backup_path),
        "created_at": datetime.now(UTC).isoformat(),
    }
    manifest_path = backup_path.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def verify_manifest(backup_path: Path) -> bool:
    """تطابق sha/size فایل با مانیفست."""
    manifest_path = backup_path.with_suffix(".manifest.json")
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    if manifest.get("file") != backup_path.name:
        return False
    if backup_path.stat().st_size != manifest.get("size_bytes"):
        return False
    return sha256_file(backup_path) == manifest.get("sha256")


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _db_env() -> dict[str, str]:
    """خواندن اتصال از .env (بدون چاپ مقدار)."""
    env: dict[str, str] = {}
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


def cmd_backup(backup_dir: Path, keep: int) -> int:
    backup_dir.mkdir(parents=True, exist_ok=True)
    filename = backup_filename()
    target = backup_dir / filename
    env = _db_env()
    user = env.get("POSTGRES_USER", "gi_user")
    dbname = env.get("POSTGRES_DB", "globalintelligence")
    print(f"backup -> {target}")
    proc = _run(
        ["docker", "exec", "gi_postgres", "pg_dump", "-U", user, "-Fc", "-f",
         f"/tmp/{filename}", dbname]
    )
    if proc.returncode != 0:
        print(f"pg_dump failed: {proc.stderr[-500:]}")
        return 1
    proc = _run(["docker", "cp", f"gi_postgres:/tmp/{filename}", str(target)])
    if proc.returncode != 0:
        print(f"docker cp failed: {proc.stderr[-500:]}")
        return 1
    _run(["docker", "exec", "gi_postgres", "rm", f"/tmp/{filename}"])
    if target.stat().st_size == 0:
        print("backup file is empty")
        return 1
    manifest = write_manifest(target)
    print(f"manifest: {manifest} sha={sha256_file(target)[:12]}...")
    for old in select_for_rotation(
        sorted(p.name for p in backup_dir.glob("gi_backup-*.dump")), keep
    ):
        (backup_dir / old).unlink(missing_ok=True)
        (backup_dir / old).with_suffix(".manifest.json").unlink(missing_ok=True)
        print(f"rotated: {old}")
    return 0


def cmd_restore(backup_file: Path, target_db: str, yes: bool = False) -> int:
    if not backup_file.exists():
        print("backup file not found")
        return 1
    if not verify_manifest(backup_file):
        print("manifest mismatch; refusing to restore")
        return 1
    if not yes:
        print("refusing without --yes (destructive guard)")
        return 1
    env = _db_env()
    user = env.get("POSTGRES_USER", "gi_user")
    print(f"restore {backup_file.name} -> {target_db}")
    _run([
        "docker", "exec", "gi_postgres", "psql", "-U", user, "-d", "postgres",
        "-c", f"DROP DATABASE IF EXISTS {target_db};",
    ])
    proc = _run([
        "docker", "exec", "gi_postgres", "psql", "-U", user, "-d", "postgres",
        "-c", f"CREATE DATABASE {target_db};",
    ])
    if proc.returncode != 0:
        print(f"create failed: {proc.stderr[-300:]}")
        return 1
    _run(["docker", "cp", str(backup_file), "gi_postgres:/tmp/restore.dump"])
    proc = _run([
        "docker", "exec", "gi_postgres", "pg_restore", "-U", user,
        "-d", target_db, "--no-owner", "/tmp/restore.dump",
    ])
    _run(["docker", "exec", "gi_postgres", "rm", "/tmp/restore.dump"])
    if proc.returncode != 0:
        print(f"pg_restore warnings/errors: {proc.stderr[-500:]}")
        return 1
    print("restore ok")
    return 0


def table_counts(target_db: str) -> dict[str, int]:
    env = _db_env()
    user = env.get("POSTGRES_USER", "gi_user")
    out: dict[str, int] = {}
    for table in KEY_TABLES:
        proc = _run([
            "docker", "exec", "gi_postgres", "psql", "-U", user, "-d", target_db,
            "-t", "-A", "-c", f"SELECT count(*) FROM {table};",
        ])
        try:
            out[table] = int(proc.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            out[table] = -1
    return out


def cmd_verify(target_db: str) -> int:
    env = _db_env()
    live_db = env.get("POSTGRES_DB", "globalintelligence")
    live = table_counts(live_db)
    restored = table_counts(target_db)
    mismatches = {
        t: (live.get(t), restored.get(t))
        for t in KEY_TABLES
        if live.get(t) != restored.get(t)
    }
    print(json.dumps({"live": live, "restored": restored}, indent=2))
    if mismatches:
        print(f"MISMATCH: {mismatches}")
        return 1
    print("verify ok: all counts match")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PostgreSQL backup/restore/verify")
    sub = parser.add_subparsers(dest="command", required=True)

    p_backup = sub.add_parser("backup")
    p_backup.add_argument("--dir", default="backups", dest="backup_dir")
    p_backup.add_argument("--keep", type=int, default=7)

    p_restore = sub.add_parser("restore")
    p_restore.add_argument("--file", required=True)
    p_restore.add_argument("--target-db", default="gi_restore_test", dest="target_db")
    p_restore.add_argument("--yes", action="store_true")

    p_verify = sub.add_parser("verify")
    p_verify.add_argument("--target-db", default="gi_restore_test", dest="target_db")

    args = parser.parse_args(argv)
    if args.command == "backup":
        return cmd_backup(Path(args.backup_dir), args.keep)
    if args.command == "restore":
        return cmd_restore(Path(args.file), args.target_db, args.yes)
    if args.command == "verify":
        return cmd_verify(args.target_db)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
