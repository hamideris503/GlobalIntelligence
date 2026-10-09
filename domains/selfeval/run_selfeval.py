"""Run platform self-evaluation (Phase 39 CLI).

اجرا:
    python -m domains.selfeval.run_selfeval
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.selfeval.service import SelfEvaluationService


def main() -> int:
    parser = argparse.ArgumentParser(description="Run platform self-evaluation")
    _ = parser.parse_args()

    session = get_session_factory()()
    try:
        outcome = SelfEvaluationService(session).run()
    finally:
        session.close()
    print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
