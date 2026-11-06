"""Re-extract events whose AI extraction previously failed.

Dry-run by default. Does NOT call any AI/network: it re-applies the
deterministic type/location rules to events that have empty fields, and
records the failure reason. Once a real provider is configured, replace the
deterministic step with EventExtractor for these events (max N per run).
"""
from __future__ import annotations

import argparse

from sqlalchemy.orm import Session

from backend.database.session import get_engine
from scripts.backfill_event_geo import run_session


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    session = Session(bind=get_engine())
    try:
        run_session(session, apply=args.apply, limit=args.limit)
    finally:
        session.close()


if __name__ == "__main__":
    main()
