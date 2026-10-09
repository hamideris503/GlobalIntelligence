"""Iran briefing bundle (Phase 33 CLI).

اجرا:
    python -m domains.iran.run_brief
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.iran.brief import IranModeService


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Iran briefing bundle")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        brief = IranModeService(session).brief(limit=args.limit)
    finally:
        session.close()
    print(json.dumps(brief.as_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
