"""Tests for Retention & Disk Monitoring (Stage 100)."""

from __future__ import annotations

import shutil
from unittest.mock import patch

from domains.retention import RetentionService, disk_status
from domains.retention.policy import PROTECTED_ENTITIES, RetentionPolicy
from tests.conftest import TestingSession


def test_protected_entities_never_candidate():
    assert "event" in PROTECTED_ENTITIES
    assert "claim" in PROTECTED_ENTITIES
    assert "evidence" in PROTECTED_ENTITIES
    assert "forecast" in PROTECTED_ENTITIES
    assert "outcome" in PROTECTED_ENTITIES
    assert "audit" in PROTECTED_ENTITIES
    p = RetentionPolicy()
    for e in PROTECTED_ENTITIES:
        assert p.is_protected(e)


def test_disk_status_returns_fields():
    st = disk_status(".")
    assert "total" in st
    assert "used" in st
    assert "free" in st
    assert "used_percent" in st


def test_dry_run_no_deletion():
    session = TestingSession()
    try:
        out = RetentionService(session).dry_run().as_dict()
        assert out["note"] == "dry-run only; no deletion performed"
        assert "candidates" in out
        assert "protected" in out
        assert "disk" in out
        assert out["total_candidates"] >= 0
        # protected list includes event/claim/etc
        assert "event" in out["protected"]
    finally:
        session.close()


def test_dry_run_candidate_groups():
    session = TestingSession()
    try:
        out = RetentionService(session).dry_run().as_dict()
        entities = {c["entity"] for c in out["candidates"]}
        assert "document" in entities
        assert "market_observation" in entities
        assert "job_run" in entities
        assert "article_dispatch_terminal" in entities
    finally:
        session.close()


def test_disk_alert_threshold():
    p = RetentionPolicy(disk_warn_percent=70.0)
    svc = None
    from domains.retention.service import RetentionService
    session = TestingSession()
    try:
        svc = RetentionService(session, policy=p)
        # mock disk_status to high usage
        with patch("domains.retention.service.disk_status", return_value={"used_percent": 80.0}):
            assert svc.disk_alert_needed() is True
        with patch("domains.retention.service.disk_status", return_value={"used_percent": 50.0}):
            assert svc.disk_alert_needed() is False
    finally:
        session.close()
