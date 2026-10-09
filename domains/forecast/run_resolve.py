"""Resolve forecast outcomes (Phase 27 CLI).

اجرا:
    python -m domains.forecast.run_resolve
    python -m domains.forecast.run_resolve --target macro:inflation:USA
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.forecast.outcome import OutcomeEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve forecast outcomes")
    parser.add_argument("--target", type=str, default=None)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = OutcomeEngine(session).resolve_all(target=args.target)
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
