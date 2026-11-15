"""PostgreSQL/SQLite backup/restore/verify (Phase 45 + اجرای محلی Windows).

- `backup`: pg_dump (custom format) یا backup آنلاین SQLite + manifest (sha256/size) + rotation.
- `restore`: بازگردانی به هدف (پیش‌فرض temp) با محافظ تأیید.
- `verify`: مقایسه‌ی شمارش جدول‌های کلیدی مبدأ/مقصد پس از restore.

موتور به‌صورت خودکار از `DATABASE_URL` در `.env` تشخیص داده می‌شود؛
برای SQLite هیچ Docker/pg_dump لازم نیست (پشتیبانی از نصب محلی Windows).

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
    "alert_rules", "alerts", "briefings", "job_runs", "audit_records",
    "self_evaluations", "learning_insights",
]

# نام مجاز دیتابیس هدف (جلوگیری از SQL injection از آرگومان CLI)
def valid_target_db(name: str) -> bool:
    """شناسه‌ی معتبر Postgres (حروف/عدد/آندرلاین، شروع با حرف/آندرلاین)."""
    import re

    return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name or "") is not None


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


def _container() -> str:
    """نام کانتینر postgres (پیش‌فرض gi_postgres؛ staging: gi_staging_postgres)."""
    import os

    return os.environ.get("PG_CONTAINER", "gi_postgres")


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


def _database_url() -> str:
    """DATABASE_URL از محیط یا `.env` (مقدار چاپ نمی‌شود)."""
    import os

    return os.environ.get("DATABASE_URL") or _db_env().get("DATABASE_URL", "")


def sqlite_path_from_url(url: str) -> Path | None:
    """مسیر فایل از DSN SQLite؛ None اگر موتور SQLite نباشد."""
    if not url.startswith("sqlite"):
        return None
    raw = url.split("sqlite:///", 1)[1] if "sqlite:///" in url else url.split("sqlite://", 1)[1]
    return Path(raw)


def _sqlite_backup_filename(now: datetime | None = None) -> str:
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    return f"gi_backup-{stamp}.sqlite3"


def cmd_sqlite_backup(db_path: Path, backup_dir: Path, keep: int) -> int:
    """backup آنلاین SQLite (بدون توقف سرویس) + manifest + rotation."""
    import sqlite3

    if not db_path.exists():
        print(f"sqlite database not found: {db_path}")
        return 1
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / _sqlite_backup_filename()
    source = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    if target.stat().st_size == 0:
        print("backup file is empty")
        return 1
    manifest = write_manifest(target)
    print(f"sqlite backup -> {target} sha={sha256_file(target)[:12]}... manifest={manifest}")
    for old in select_for_rotation(
        sorted(p.name for p in backup_dir.glob("gi_backup-*.sqlite3")), keep
    ):
        (backup_dir / old).unlink(missing_ok=True)
        (backup_dir / old).with_suffix(".manifest.json").unlink(missing_ok=True)
        print(f"rotated: {old}")
    return 0


def sqlite_integrity_ok(path: Path) -> bool:
    import sqlite3

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            return conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        print(f"sqlite integrity check failed: {type(exc).__name__}")
        return False


def cmd_sqlite_restore(backup_file: Path, target_db: str, yes: bool = False) -> int:
    """بازگردانی فایل SQLite به یک مسیر هدف (پیش‌فرض کنار خود فایل)."""
    import shutil

    if not backup_file.exists():
        print("backup file not found")
        return 1
    if not verify_manifest(backup_file):
        print("manifest mismatch; refusing to restore")
        return 1
    if not yes:
        print("refusing without --yes (destructive guard)")
        return 1
    if not sqlite_integrity_ok(backup_file):
        print("backup integrity check failed; refusing to restore")
        return 1
    target = Path(target_db)
    if target.suffix not in (".db", ".sqlite3"):
        target = target.with_suffix(".sqlite3")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_file, target)
    if not sqlite_integrity_ok(target):
        print("restored database failed integrity check")
        return 1
    print(f"sqlite restore ok -> {target}")
    return 0


def sqlite_table_counts(path: Path) -> dict[str, int]:
    import sqlite3

    out: dict[str, int] = {}
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        for table in KEY_TABLES:
            try:
                out[table] = int(conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0])
            except Exception:  # noqa: BLE001 — جدول در این schema نیست
                out[table] = -1
    finally:
        conn.close()
    return out


def cmd_backup(backup_dir: Path, keep: int) -> int:
    db_path = sqlite_path_from_url(_database_url())
    if db_path is not None:
        return cmd_sqlite_backup(db_path, backup_dir, keep)
    backup_dir.mkdir(parents=True, exist_ok=True)
    filename = backup_filename()
    target = backup_dir / filename
    env = _db_env()
    user = env.get("POSTGRES_USER", "gi_user")
    dbname = env.get("POSTGRES_DB", "globalintelligence")
    print(f"backup -> {target}")
    proc = _run(
        ["docker", "exec", _container(), "pg_dump", "-U", user, "-Fc", "-f",
         f"/tmp/{filename}", dbname]
    )
    if proc.returncode != 0:
        print(f"pg_dump failed: {proc.stderr[-500:]}")
        return 1
    proc = _run(["docker", "cp", f"{_container()}:/tmp/{filename}", str(target)])
    if proc.returncode != 0:
        print(f"docker cp failed: {proc.stderr[-500:]}")
        return 1
    _run(["docker", "exec", _container(), "rm", f"/tmp/{filename}"])
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
    if backup_file.suffix == ".sqlite3":
        return cmd_sqlite_restore(backup_file, target_db, yes)
    if not backup_file.exists():
        print("backup file not found")
        return 1
    if not verify_manifest(backup_file):
        print("manifest mismatch; refusing to restore")
        return 1
    if not yes:
        print("refusing without --yes (destructive guard)")
        return 1
    if not valid_target_db(target_db):
        print(f"REFUSED: unsafe target_db name: {target_db!r}")
        return 1
    env = _db_env()
    user = env.get("POSTGRES_USER", "gi_user")
    print(f"restore {backup_file.name} -> {target_db}")
    container = _container()
    _run([
        "docker", "exec", container, "psql", "-U", user, "-d", "postgres",
        "-c", f"DROP DATABASE IF EXISTS {target_db};",
    ])
    proc = _run([
        "docker", "exec", container, "psql", "-U", user, "-d", "postgres",
        "-c", f"CREATE DATABASE {target_db};",
    ])
    if proc.returncode != 0:
        print(f"create failed: {proc.stderr[-300:]}")
        return 1
    _run(["docker", "cp", str(backup_file), f"{_container()}:/tmp/restore.dump"])
    proc = _run([
        "docker", "exec", _container(), "pg_restore", "-U", user,
        "-d", target_db, "--no-owner", "/tmp/restore.dump",
    ])
    _run(["docker", "exec", _container(), "rm", "/tmp/restore.dump"])
    if proc.returncode != 0:
        print(f"pg_restore warnings/errors: {proc.stderr[-500:]}")
        return 1
    print("restore ok")
    return 0


def table_counts(target_db: str) -> dict[str, int]:
    if not valid_target_db(target_db):
        raise ValueError(f"unsafe target_db name: {target_db!r}")
    env = _db_env()
    user = env.get("POSTGRES_USER", "gi_user")
    container = _container()
    out: dict[str, int] = {}
    for table in KEY_TABLES:
        proc = _run([
            "docker", "exec", container, "psql", "-U", user, "-d", target_db,
            "-t", "-A", "-c", f"SELECT count(*) FROM {table};",
        ])
        try:
            out[table] = int(proc.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            out[table] = -1
    return out


def cmd_verify(target_db: str) -> int:
    db_path = sqlite_path_from_url(_database_url())
    if db_path is not None:
        restored_path = Path(target_db)
        if restored_path.suffix not in (".db", ".sqlite3"):
            restored_path = restored_path.with_suffix(".sqlite3")
        if not db_path.exists():
            print(f"live sqlite database not found: {db_path}")
            return 1
        if not restored_path.exists():
            print(f"restored sqlite database not found: {restored_path}")
            return 1
        live = sqlite_table_counts(db_path)
        restored = sqlite_table_counts(restored_path)
        mismatches = {
            t: (live.get(t), restored.get(t))
            for t in KEY_TABLES if live.get(t) != restored.get(t)
        }
        print(json.dumps({"live": live, "restored": restored}, indent=2))
        if mismatches:
            print(f"MISMATCH: {mismatches}")
            return 1
        print("verify ok: all counts match")
        return 0
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
    parser = argparse.ArgumentParser(description="Backup/restore/verify (PostgreSQL یا SQLite)")
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
