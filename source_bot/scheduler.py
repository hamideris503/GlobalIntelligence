"""Scheduler — یک مسئول زمان‌بندی (n8n موجود مالک cron می‌ماند؛ این ماژول tick محلی است)."""
from __future__ import annotations

import asyncio

from source_bot.runner import run_forever


def main() -> None:
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
