"""Make rule-based decisions (Phase 32 CLI).

اجرا:
    python -m domains.decision.run_decide
    python -m domains.decision.run_decide --targets macro:inflation:USA market:WTI
    python -m domains.decision.run_decide --from-debate <run_id>  # پیشنهاد از debate (Step 5)
"""
from __future__ import annotations

import argparse
import json
import uuid

from backend.database.session import get_session_factory
from domains.decision.engine import DecisionEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Make rule-based decisions")
    parser.add_argument("--targets", nargs="*", default=None)
    parser.add_argument("--horizon", type=str, default="short")
    parser.add_argument("--from-debate", type=str, default=None,
                        help="debate run id -> proposal with hard gates")
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        if args.from_debate:
            from domains.decision.debate_bridge import build_proposal

            outcome = build_proposal(session, uuid.UUID(args.from_debate))
            print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
        else:
            outcome = DecisionEngine(session).run(
                targets=args.targets, horizon=args.horizon
            )
            print(json.dumps(outcome.as_dict(), ensure_ascii=False, indent=2))
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
