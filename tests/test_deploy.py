"""Tests for VPS deploy planner (Phase 48).

منطق خالص (ساخت فرمان، محافظ .env) بدون سرور آزمون می‌شود؛
استقرار زنده BLOCKED است (بدون دسترسی به VPS).
"""
from __future__ import annotations

from pathlib import Path

from scripts.deploy_vps import (
    build_steps,
    check_local_files,
    check_no_env,
    ssh_base,
)


def test_ssh_base_batch_mode() -> None:
    cmd = ssh_base("h", "u", None)
    assert "BatchMode=yes" in " ".join(cmd)
    assert cmd[-1] == "u@h"
    with_key = ssh_base("h", "u", "/k")
    assert "-i" in with_key and "/k" in with_key


def test_build_steps_order_and_count() -> None:
    steps = build_steps("h", "u", None)
    assert len(steps) == 5
    assert "docker compose" in " ".join(steps[3])
    assert "health" in " ".join(steps[4])


def test_check_no_env_refuses() -> None:
    assert check_no_env(["docker-compose.yml", ".env.example"]) == []
    assert check_no_env(["x", ".env"]) == [".env"]
    assert check_no_env([".env.production"]) == [".env.production"]


def test_check_local_files() -> None:
    missing = check_local_files(Path("."))
    assert missing == []


def test_transfer_step_has_no_env() -> None:
    steps = build_steps("h", "u", None)
    transfer = steps[2]
    assert check_no_env(transfer) == []
    joined = " ".join(transfer)
    assert "docker-compose.prod.yml" in joined
