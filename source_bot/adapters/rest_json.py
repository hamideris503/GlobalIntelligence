"""REST/JSON adapter — HTTPX با ETag/Last-Modified، pagination، مدیریت خطاها.

کلید از env خوانده می‌شود؛ secret هرگز لاگ نمی‌شود.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from domains.news.fetchers import RawItem
from source_bot.security import assert_public_host, validate_url


@dataclass
class JsonResult:
    items: list[RawItem]
    status: str  # ok | not_modified | auth_required | http_error
    detail: str = ""
    etag: str | None = None
    last_modified: str | None = None


def _parse_date(v: object) -> datetime | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        dt = parsedate_to_datetime(v)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except Exception:  # noqa: BLE001
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            return None


_FIELD_ALIASES = {
    "title": ("title", "headline", "name"),
    "url": ("url", "link", "canonical_url"),
    "text": ("body", "text", "content", "description", "summary"),
    "author": ("author", "byline", "creator"),
    "published": ("published_at", "published", "date", "created_at"),
    "external_id": ("id", "guid", "external_id", "uuid"),
}


def pick(d: dict, keys: tuple[str, ...]) -> object:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


class RestJsonAdapter:
    name = "rest_json"

    def __init__(self, timeout: float = 20.0, max_bytes: int = 5_000_000,
                 max_redirects: int = 3) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self._etag: dict[str, str] = {}
        self._last_mod: dict[str, str] = {}

    async def fetch(
        self,
        *,
        url: str | None,
        limit: int = 20,
        api_key_env: str | None = None,
        items_path: str | None = None,
        max_pages: int = 3,
    ) -> JsonResult:
        check = validate_url(url or "")
        if not check.ok:
            return JsonResult([], "http_error", f"refusing url: {check.reason}")
        assert url
        from urllib.parse import urlparse as _up

        headers = {"User-Agent": "GlobalIntelligenceBot/0.1", "Accept": "application/json"}
        if url in self._etag:
            headers["If-None-Match"] = self._etag[url]
        if url in self._last_mod:
            headers["If-Modified-Since"] = self._last_mod[url]
        if api_key_env:
            key = os.getenv(api_key_env or "")
            if not key:
                return JsonResult([], "auth_required", f"missing credential: {api_key_env}")
            headers["Authorization"] = f"Bearer {key}"

        items: list[RawItem] = []
        next_url: str | None = url
        pages = 0
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False,
                                         max_redirects=self.max_redirects) as client:
                while next_url and pages < max_pages and len(items) < limit:
                    pages += 1
                    resp = await client.get(next_url, headers=headers)
                    if resp.status_code == 304:
                        return JsonResult([], "not_modified", "not modified")
                    if resp.status_code in (401, 403):
                        return JsonResult([], "auth_required", f"http_{resp.status_code}")
                    if resp.status_code == 429:
                        return JsonResult(items, "http_error", "http_429 rate limited")
                    if resp.status_code == 404:
                        return JsonResult(items, "http_error", "http_404")
                    if resp.status_code in (301, 302, 303, 307, 308):
                        loc = resp.headers.get("location")
                        if not loc:
                            return JsonResult(items, "http_error", "redirect without location")
                        chk = validate_url(loc)
                        if not chk.ok:
                            return JsonResult(items, "http_error", f"blocked redirect: {chk.reason}")
                        assert_public_host((_up(loc).hostname or "").lower())
                        next_url = loc
                        continue
                    if resp.status_code >= 500:
                        return JsonResult(items, "http_error", f"http_{resp.status_code}")
                    resp.raise_for_status()
                    if resp.headers.get("etag"):
                        self._etag[next_url] = resp.headers["etag"]
                    if resp.headers.get("last-modified"):
                        self._last_mod[next_url] = resp.headers["last-modified"]
                    if len(resp.content) > self.max_bytes:
                        return JsonResult(items, "http_error", "response too big")
                    data = resp.json()
                    rows: object = data
                    if items_path:
                        for part in items_path.split("."):
                            rows = rows.get(part, []) if isinstance(rows, dict) else []
                    if isinstance(rows, dict):
                        for k in ("items", "results", "data", "articles"):
                            if isinstance(rows.get(k), list):
                                rows = rows[k]
                                break
                    if not isinstance(rows, list):
                        rows = [rows]
                    for row in rows:
                        if len(items) >= limit:
                            break
                        if not isinstance(row, dict):
                            continue
                        items.append(
                            RawItem(
                                title=str(pick(row, _FIELD_ALIASES["title"]) or "") or None,
                                url=str(pick(row, _FIELD_ALIASES["url"]) or "") or None,
                                raw_text=str(pick(row, _FIELD_ALIASES["text"]) or "") or None,
                                published_at=_parse_date(pick(row, _FIELD_ALIASES["published"])),
                                author=str(pick(row, _FIELD_ALIASES["author"]) or "") or None,
                                raw_payload=json.dumps(row, ensure_ascii=False, default=str),
                                metadata={
                                    "external_id": pick(row, _FIELD_ALIASES["external_id"]),
                                    "adapter": "rest_json",
                                },
                            )
                        )
                    next_url = None
                    if isinstance(data, dict):
                        nxt = data.get("next") or data.get("next_page")
                        if isinstance(nxt, str) and validate_url(nxt).ok:
                            next_url = nxt
            return JsonResult(items, "ok", "", self._etag.get(url), self._last_mod.get(url))
        except httpx.TimeoutException:
            return JsonResult(items, "http_error", "timeout")
        except Exception as exc:  # noqa: BLE001 — فقط نوع خطا، بدون secret
            return JsonResult(items, "http_error", f"fetch_error:{type(exc).__name__}")
