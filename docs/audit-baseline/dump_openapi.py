"""Dump the real API contract of the FastAPI app to stdout (read-only).

Used by UI-00 / UI_API_MAPPING to build the UI → API → DB → Test matrix from the
application itself instead of from guesses about router files.

    python docs/audit-baseline/dump_openapi.py            # paths + operations
    python docs/audit-baseline/dump_openapi.py --json     # full OpenAPI document

Requires the app to be importable (no DB connection is made by `create_app()`).
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# Import-time settings validation needs these; values are placeholders only.
os.environ.setdefault("MOCK_MODE", "true")
os.environ.setdefault("API_KEY", "audit-placeholder")
os.environ.setdefault("SECRET_KEY", "audit-placeholder-" + "x" * 32)

from backend.main import create_app  # noqa: E402

METHODS = ("get", "post", "put", "patch", "delete")


def main() -> int:
    spec = create_app().openapi()
    if "--json" in sys.argv:
        json.dump(spec, sys.stdout, ensure_ascii=False, indent=2)
        return 0

    paths = spec.get("paths", {})
    operations = 0
    print(f"# paths={len(paths)}")
    for path in sorted(paths):
        for method, op in paths[path].items():
            if method not in METHODS:
                continue
            operations += 1
            params = ",".join(p.get("name", "") for p in op.get("parameters", []))
            print(f"{method.upper():6} {path:46} [{params}]")
    print(f"# operations={operations}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
