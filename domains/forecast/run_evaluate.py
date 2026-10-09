"""Evaluate resolved forecasts (Phase 28 CLI).

اجرا:
    python -m domains.forecast.run_evaluate
    python -m domains.forecast.run_evaluate --target macro:inflation:USA
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.forecast.evaluation import EvaluationEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate resolved forecasts")
    parser.add_argument("--target", type=str, default=None)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--model", type=str, default=None)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        engine = EvaluationEngine(session)
        if args.summary:
            out = engine.summary(target=args.target, model=args.model)
        else:
            out = engine.run(target=args.target).as_dict()
    finally:
        session.close()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
