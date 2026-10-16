"""RSS autodiscovery (evidence-based, no guessing) + validation.

For VERIFIED media sources with empty rss_url: parse homepage <link rel=alternate>,
validate the feed with check_rss, store ONLY if valid. Polite delay.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time

sys.path.insert(0, ".")

import httpx
from sqlalchemy import select

from backend.database.models.source import Source
from backend.database.session import get_session_factory
from domains.news.source_verify import BROWSER_UA, TIMEOUT, check_rss

LINK_RE = re.compile(
    r'<link[^>]+rel=["\']alternate["\'][^>]*>', re.IGNORECASE)
HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
TYPE_RE = re.compile(r'type=["\']([^"\']+)["\']', re.IGNORECASE)


def discover(html: str, base: str) -> list[str]:
    from urllib.parse import urljoin

    found = []
    for tag in LINK_RE.findall(html):
        typ = (TYPE_RE.search(tag).group(1) if TYPE_RE.search(tag) else "").lower()
        href = HREF_RE.search(tag)
        if not href:
            continue
        if "rss" in typ or "atom" in typ or "xml" in typ:
            abs_url = urljoin(base, href.group(1))
            if abs_url.startswith(("http://", "https://")) and abs_url not in found:
                found.append(abs_url)
    return found[:3]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--delay", type=float, default=1.5)
    args = parser.parse_args()

    session = get_session_factory()()
    stats = {"checked": 0, "rss_valid": 0, "rss_invalid": 0, "no_link": 0}
    try:
        rows = list(session.execute(
            select(Source)
            .where(Source.validation_status == "VERIFIED",
                   Source.homepage_url.is_not(None))
            .order_by(Source.name)
            .limit(args.limit)
        ).scalars().all())
        print(f"candidates: {len(rows)}", flush=True)
        for i, src in enumerate(rows):
            if src.rss_url:
                continue
            stats["checked"] += 1
            try:
                with httpx.Client(timeout=TIMEOUT,
                                  headers={"User-Agent": BROWSER_UA}) as client:
                    resp = client.get(src.canonical_url or src.homepage_url or "")
                candidates = discover(resp.text[:500000],
                                      src.canonical_url or src.homepage_url or "")
                if not candidates:
                    stats["no_link"] += 1
                for feed in candidates:
                    chk = check_rss(feed, timeout=TIMEOUT)
                    if chk.ok:
                        src.rss_url = feed
                        session.commit()
                        stats["rss_valid"] += 1
                        print(f"[{i + 1}] {src.name}: RSS {feed}", flush=True)
                        break
                else:
                    if candidates:
                        stats["rss_invalid"] += 1
                        print(f"[{i + 1}] {src.name}: feed links invalid", flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"[{i + 1}] {src.name}: {type(exc).__name__}", flush=True)
            time.sleep(args.delay)
    finally:
        session.close()
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
