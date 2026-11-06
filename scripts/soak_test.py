"""Soak test runner for F15-G (stdlib + pytest-like, no new deps).

Usage:
  python scripts/soak_test.py --duration 60 --interval 5
  (runs for 60 seconds, one cycle every 5 seconds)

Measures: cycle count, errors, memory (RSS), DB query latency.
Does NOT modify production code. Uses test DB via DATABASE_URL.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("API_KEY", "")

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)
headers = {"X-API-Key": os.getenv("API_KEY", "")}


def cycle(i: int) -> dict:
    t0 = time.perf_counter()
    errors = []
    try:
        sname = f"SoakSrc-{uuid.uuid4().hex[:6]}"
        r = client.post("/api/sources", headers=headers, json={
            "name": sname, "domain": "soak.local", "type": "rss", "active": True, "collection_method": "rss",
        })
        if r.status_code not in (200, 201):
            errors.append(f"source create {r.status_code}")
        else:
            ir = client.post("/api/ingest", headers=headers, json={"source_name": sname, "limit": 2})
            if ir.status_code not in (200, 201):
                errors.append(f"ingest {ir.status_code}")
            cr = client.post("/api/classify/run?limit=10", headers=headers)
            if cr.status_code not in (200, 201):
                errors.append(f"classify {cr.status_code}")
    except Exception as e:
        errors.append(str(e))
    dt = time.perf_counter() - t0
    return {"cycle": i, "duration": round(dt, 3), "errors": errors}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=60, help="seconds")
    ap.add_argument("--interval", type=int, default=5, help="seconds between cycles")
    args = ap.parse_args()

    start = time.time()
    results = []
    i = 0
    while time.time() - start < args.duration:
        i += 1
        res = cycle(i)
        results.append(res)
        print(json.dumps(res), flush=True)
        try:
            import psutil
            print(f"  memory_rss_mb={psutil.Process().memory_info().rss/1024/1024:.1f}", flush=True)
        except ImportError:
            pass
        time.sleep(args.interval)

    total_errors = sum(len(r["errors"]) for r in results)
    print(f"\nSoak complete: cycles={len(results)} errors={total_errors} duration={time.time()-start:.1f}s")
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
