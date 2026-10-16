"""Run a debate (Step 3 CLI).

اجرا:
    python -m domains.debate.run_debate --target market:WTI --dry-run
    python -m domains.debate.run_debate --target market:WTI --live   # فراخوانی واقعی LLM

بدون --live هیچ تماس واقعی گرفته نمی‌شود (پیش‌فرض امن).
"""
from __future__ import annotations

import argparse
import asyncio
import json

from backend.database.session import get_session_factory
from domains.debate.engine import DebateEngine, load_debate_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a multi-agent debate")
    parser.add_argument("--target", type=str, default=None)
    parser.add_argument("--horizon-days", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--live", action="store_true",
                        help="allow real LLM calls (required for a real run)")
    parser.add_argument("--max-rounds", type=int, default=None)
    args = parser.parse_args()

    if not args.dry_run and not args.live:
        parser.error("refusing real LLM calls without --live (use --dry-run for estimate)")

    session = get_session_factory()()
    try:
        engine = DebateEngine(session)
        targets = [args.target] if args.target else [
            t["target"] for t in load_debate_config().get("targets", [])
        ]
        if not targets:
            parser.error("no target given and none in config/debate.toml")
        for target in targets:
            horizon = args.horizon_days
            outcome = asyncio.run(engine.run(
                target=target, horizon_days=horizon,
                dry_run=args.dry_run, max_rounds=args.max_rounds,
            ))
            print(json.dumps({"target": target, **outcome.as_dict()}, ensure_ascii=False))
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
