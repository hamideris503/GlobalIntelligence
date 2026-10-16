"""GlobalIntelligence — Flag mock rows (Step 2).

ردیف‌های نمونه (mock) را شمارش و فهرست می‌کند؛ **هیچ‌چیز را حذف نمی‌کند**.
حذف فقط با تأیید صریح کاربر انجام می‌شود.

پوشش:
- MarketObservation: source_name='mock' یا metadata دارای "mock": true
- MacroObservation: source_name='mock' یا metadata دارای "mock": true
- Article: classification_meta دارای is_mock=true

اجرا:
    python scripts/flag_mock_rows.py [--limit 50]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass


def _has_mock_flag(raw: str | None) -> bool:
    if not raw:
        return False
    try:
        meta = json.loads(raw)
    except Exception:  # noqa: BLE001
        return '"mock": true' in raw or '"is_mock": true' in raw
    if isinstance(meta, dict):
        return meta.get("mock") is True or meta.get("is_mock") is True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Count/list mock rows (read-only)")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)

    from sqlalchemy import select

    from backend.database.models.article import Article
    from backend.database.models.market import MacroObservation, MarketObservation
    from backend.database.session import get_session_factory

    session = get_session_factory()()
    try:
        print("== MarketObservation ==")
        mrows = session.execute(select(MarketObservation)).scalars().all()
        mmock = [
            r for r in mrows
            if (r.source_name or "") == "mock" or _has_mock_flag(r.raw)
        ]
        print(f"total={len(mrows)} mock={len(mmock)}")
        for r in mmock[: args.limit]:
            print(f"  {r.symbol} src={r.source_name} obs={r.observed_at} value={r.value}")

        print("== MacroObservation ==")
        grows = session.execute(select(MacroObservation)).scalars().all()
        gmock = [
            r for r in grows
            if (r.source_name or "") == "mock" or _has_mock_flag(r.raw)
        ]
        print(f"total={len(grows)} mock={len(gmock)}")
        for r in gmock[: args.limit]:
            print(f"  {r.indicator}/{r.country}/{r.period} src={r.source_name} value={r.value}")

        print("== Article (is_mock in classification_meta) ==")
        arows = session.execute(select(Article)).scalars().all()
        amock = [a for a in arows if _has_mock_flag(a.classification_meta)]
        print(f"total={len(arows)} mock_classified={len(amock)}")
        for a in amock[: args.limit]:
            title = (a.title or "")[:80]
            print(f"  {str(a.id)[:8]} {title}")

        print("NOTE: nothing was deleted. Deletion requires explicit user approval.")
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
