"""Tests for backup helpers (Phase 45).

توابع خالص (نام‌گذاری/rotation/مانیفست) بدون Docker آزمون می‌شوند؛
مسیر زنده‌ی dump/restore در تأیید زنده اجرا می‌شود، نه pytest.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.db_backup import (
    backup_filename,
    select_for_rotation,
    verify_manifest,
    write_manifest,
)


def test_backup_filename_format() -> None:
    name = backup_filename(now=datetime(2026, 10, 9, 12, 0, tzinfo=UTC))
    assert name == "gi_backup-20261009-120000.dump"


def test_select_for_rotation() -> None:
    files = [f"gi_backup-2026100{i}-000000.dump" for i in range(1, 6)]
    assert select_for_rotation(files, keep=7) == []
    assert select_for_rotation(files, keep=2) == files[:3]
    assert select_for_rotation([], keep=3) == []
    with pytest.raises(ValueError):
        select_for_rotation(files, keep=0)


def test_manifest_roundtrip(tmp_path: Path) -> None:
    target = tmp_path / "gi_backup-20261009-120000.dump"
    target.write_bytes(b"fake-dump-bytes")
    manifest = write_manifest(target)
    assert manifest.exists()
    assert verify_manifest(target) is True
    target.write_bytes(b"tampered")
    assert verify_manifest(target) is False


def test_verify_missing_manifest(tmp_path: Path) -> None:
    target = tmp_path / "x.dump"
    target.write_bytes(b"data")
    assert verify_manifest(target) is False
