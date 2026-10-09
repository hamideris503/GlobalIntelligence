"""Analyze risks (Phase 31 CLI).

اجرا:
    python -m domains.risk.run_analyze
    python -m domains.risk.run_analyze --period 2026-10
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.risk.analysis import RiskEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze risks")
    parser.add_argument("--period", type=str, default=None)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = RiskEngine(session).analyze_all(period=args.period)
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
