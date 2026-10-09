"""Analyze macro series (Phase 21 CLI).

اجرا:
    python -m domains.macro.run_analyze
    python -m domains.macro.run_analyze --indicator inflation --country USA
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.macro.analysis import MacroEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze macro series")
    parser.add_argument("--indicator", type=str, default=None)
    parser.add_argument("--country", type=str, default=None)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = MacroEngine(session).analyze_all(
            indicator=args.indicator, country=args.country
        )
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
