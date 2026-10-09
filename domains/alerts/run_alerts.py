"""Evaluate alert rules (Phase 43 CLI).

اجرا:
    python -m domains.alerts.run_alerts
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.alerts.engine import AlertEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate alert rules")
    _ = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = AlertEngine(session).evaluate()
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
