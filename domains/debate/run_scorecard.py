"""Debate scorecard CLI (Step 4).

اجرا:
    python -m domains.debate.run_scorecard
    python -m domains.debate.run_scorecard --target market:WTI
"""
from __future__ import annotations

import argparse
import json
import sys

from backend.database.session import get_session_factory
from domains.debate.scorecard import ScorecardBuilder

# کنسول ویندوز ممکن است cp1256 باشد و فارسی را نتواند چاپ کند.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Debate scorecard (honest evaluation)")
    parser.add_argument("--target", type=str, default=None)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        card = ScorecardBuilder(session).build(target=args.target)
    finally:
        session.close()
    print(json.dumps(card.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
