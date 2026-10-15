"""Single authoritative Mock Mode decision (Phase A).

Precedence (unchanged semantics, one place):
1. database override (operator panel, no restart) — when readable;
2. otherwise the environment / `.env` default.

The override mechanism itself lives in `backend.ai.credentials_store`
(operator-owned); this resolver only unifies *who asks*, and falls back
to the environment default whenever the override is unavailable
(missing module/table/DB, read error) so clean builds and tests keep
working. It never consults provider selection.

Out of scope by design:
- Source Bot real-fetch path (never branches on mock mode).
- `validate_production()` fail-fast (must stay environment-based).
"""
from __future__ import annotations

from backend.core.config import get_settings


def effective_mock_mode() -> bool:
    """True یعنی حالت Mock فعال است (fetch نمونه + پذیرش خروجی mock)."""
    try:
        from backend.ai import credentials_store as _store

        return bool(_store.effective_mock_mode())
    except Exception:  # noqa: BLE001 — override unavailable: use env default
        return bool(get_settings().mock_mode)
