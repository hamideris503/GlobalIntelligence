"""Show adaptive AI routes (Phase 37 CLI).

اجرا:
    python -m domains.ai_routing.run_routes --tasks classify_article extract_relations
    python -m domains.ai_routing.run_routes --apply --tasks classify_article
"""
from __future__ import annotations

import argparse
import json

from backend.ai.gateway import get_gateway
from backend.database.session import get_session_factory
from domains.ai_routing.router import AdaptiveRouter


def main() -> int:
    parser = argparse.ArgumentParser(description="Show/apply adaptive AI routes")
    parser.add_argument("--tasks", nargs="*", default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    session = get_session_factory()()
    try:
        router = AdaptiveRouter(session)
        tasks = args.tasks or ["classify_article", "extract_relations"]
        routes = router.build_routes(tasks)
        out = {t: r.providers for t, r in routes.items()}
        if args.apply:
            get_gateway().set_routes(routes)
            out["applied"] = True
    finally:
        session.close()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
