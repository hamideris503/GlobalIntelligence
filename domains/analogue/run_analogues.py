"""Find historical analogues of a world state (Phase 20 CLI).

اجرا:
    python -m domains.analogue.run_analogues
    python -m domains.analogue.run_analogues --snapshot-id <uuid> --top-k 5 --metric cosine
"""
from __future__ import annotations

import argparse
import json

from backend.database.session import get_session_factory
from domains.analogue.engine import AnalogueService


def main() -> int:
    parser = argparse.ArgumentParser(description="Find historical analogues")
    parser.add_argument("--snapshot-id", type=str, default=None, dest="snapshot_id")
    parser.add_argument("--top-k", type=int, default=5, dest="top_k")
    parser.add_argument("--metric", type=str, default="euclidean")
    parser.add_argument("--aftermath", type=str, default=None)
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        service = AnalogueService(session)
        if args.aftermath:
            out = service.aftermath(analogue_id=args.aftermath).as_dict()
        else:
            out = service.find_analogues(
                snapshot_id=args.snapshot_id, top_k=args.top_k, metric=args.metric
            ).as_dict()
    finally:
        session.close()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
