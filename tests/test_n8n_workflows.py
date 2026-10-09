"""Tests for n8n workflow files (Phase 49).

همه‌ی فایل‌های integrations/n8n/workflows/*.json باید:
- JSON معتبر با name/id باشند؛
- id نودها یکتا و اتصالات به نود موجود ارجاع دهند؛
- نودهای httpRequest به بک‌اند، هدر X-API-Key (عبارت $env) داشته باشند.
"""
from __future__ import annotations

import json
from pathlib import Path

WF_DIR = Path(__file__).resolve().parents[1] / "integrations" / "n8n" / "workflows"


def _load_all() -> list[tuple[str, dict]]:
    files = sorted(WF_DIR.glob("*.json"))
    assert files, "no workflow files found"
    return [(f.name, json.loads(f.read_text(encoding="utf-8"))) for f in files]


def test_workflow_files_valid() -> None:
    for name, wf in _load_all():
        assert wf.get("name"), f"{name}: missing name"
        assert wf.get("id"), f"{name}: missing id (n8n 2.x requires it)"
        assert isinstance(wf.get("nodes"), list) and wf["nodes"], f"{name}: no nodes"
        assert isinstance(wf.get("connections"), dict), f"{name}: no connections"


def test_workflow_node_ids_unique() -> None:
    for name, wf in _load_all():
        ids = [n.get("id") for n in wf["nodes"]]
        assert all(ids), f"{name}: node without id"
        assert len(ids) == len(set(ids)), f"{name}: duplicate node ids"
        names = [n.get("name") for n in wf["nodes"]]
        assert all(names), f"{name}: node without name"
        assert len(names) == len(set(names)), f"{name}: duplicate node names"


def test_workflow_connections_reference_nodes() -> None:
    for fname, wf in _load_all():
        names = {n.get("name") for n in wf["nodes"]}
        for src, outputs in wf["connections"].items():
            assert src in names, f"{fname}: connection from unknown node {src}"
            for branch in outputs.get("main", []):
                for link in branch:
                    assert link.get("node") in names, (
                        f"{fname}: connection to unknown node {link.get('node')}"
                    )


def test_http_nodes_have_auth_header() -> None:
    for fname, wf in _load_all():
        for node in wf["nodes"]:
            if node.get("type") != "n8n-nodes-base.httpRequest":
                continue
            params = node.get("parameters", {})
            url = params.get("url", "")
            assert url.startswith("http://backend:8000/"), (
                f"{fname}/{node.get('name')}: unexpected url {url}"
            )
            assert params.get("sendHeaders") is True, (
                f"{fname}/{node.get('name')}: missing sendHeaders"
            )
            headers = params.get("headerParameters", {}).get("parameters", [])
            api_keys = [h for h in headers if h.get("name") == "X-API-Key"]
            assert api_keys, f"{fname}/{node.get('name')}: missing X-API-Key header"
            assert "$env.BACKEND_API_KEY" in api_keys[0].get("value", ""), (
                f"{fname}/{node.get('name')}: API key must come from env, not hardcoded"
            )


def test_schedule_triggers_have_rules() -> None:
    found = 0
    for fname, wf in _load_all():
        for node in wf["nodes"]:
            if node.get("type") == "n8n-nodes-base.scheduleTrigger":
                assert node.get("parameters", {}).get("rule"), (
                    f"{fname}: schedule without rule"
                )
                found += 1
    assert found >= 4
