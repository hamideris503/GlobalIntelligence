"""CSV adapter — دانلود کنترل‌شده، نگاشت ستون قابل تنظیم، خطای سطر ایزوله.

داده ساختگی تولید نمی‌شود و عنوان منبع دست‌نخورده می‌ماند. هویت سری زمانی
(indicator + period) در `external_id` می‌نشیند، نه در عنوان.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass

import httpx

from domains.news.fetchers import SOURCE_PROVIDED_ONLY, TEXT_STATUS, RawItem
from domains.news.source_verify import BlockedTarget, GuardedTransport, safe_get
from source_bot.security import validate_url


@dataclass
class CsvResult:
    items: list[RawItem]
    status: str
    detail: str = ""
    row_errors: int = 0


DEFAULT_MAPPING: dict[str, str] = {
    "title": "title",
    "url": "url",
    "text": "text",
    "author": "author",
    "published": "published_at",
    "external_id": "external_id",
    "indicator": "indicator",
    "period": "period",
    "value": "value",
}


class CsvAdapter:
    name = "csv"

    def __init__(self, timeout: float = 20.0, max_bytes: int = 10_000_000) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes

    async def fetch(
        self, *, url: str | None, limit: int = 200,
        mapping: dict[str, str] | None = None,
    ) -> CsvResult:
        check = validate_url(url or "")
        if not check.ok:
            return CsvResult([], "http_error", f"refusing url: {check.reason}")
        assert url
        mp = mapping or DEFAULT_MAPPING
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False,
                                         transport=GuardedTransport()) as client:
                resp = await safe_get(client, url, headers={"User-Agent": "GlobalIntelligenceBot/0.1"})
                if resp.status_code in (401, 403):
                    return CsvResult([], "auth_required", f"http_{resp.status_code}")
                resp.raise_for_status()
                if len(resp.content) > self.max_bytes:
                    return CsvResult([], "http_error", "csv too big")
                raw = resp.content
        except BlockedTarget as exc:
            return CsvResult([], "http_error", f"blocked: {exc}")
        except httpx.TimeoutException:
            return CsvResult([], "http_error", "timeout")
        except Exception as exc:  # noqa: BLE001
            return CsvResult([], "http_error", f"fetch_error:{type(exc).__name__}")

        text: str | None = None
        for enc in ("utf-8-sig", "utf-8", "cp1256", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            return CsvResult([], "http_error", "undecodable")
        items: list[RawItem] = []
        row_errors = 0
        try:
            reader = csv.DictReader(io.StringIO(text))
        except Exception:  # noqa: BLE001
            return CsvResult([], "http_error", "csv_parse_error")
        for row in (reader or []):
            if len(items) >= limit:
                break
            try:
                if not isinstance(row, dict):
                    row_errors += 1
                    continue
                low = {(k or "").strip().lower(): v for k, v in row.items()}

                def _col(name: str, _low: dict = low, _mp: dict = mp) -> str | None:
                    key = (_mp.get(name) or name).lower()
                    v = _low.get(key)
                    return str(v).strip() or None if v is not None else None

                col = _col
                body = col("text")
                meta: dict = {"adapter": "csv", "mock": False}
                if body:
                    # فیلد متنِ خودِ منبع؛ استخراج صفحهٔ مقاله رخ نداده است.
                    meta[TEXT_STATUS] = SOURCE_PROVIDED_ONLY
                if col("indicator") or col("period") or col("value"):
                    meta.update({"indicator": col("indicator"), "period": col("period"), "value": col("value")})
                title = col("title")
                ext = col("external_id")
                if meta.get("indicator") and meta.get("period"):
                    # هویت پایدار سری زمانی = شاخص + دوره (در external_id، نه در عنوان).
                    # عنوان منبع دست‌نخورده می‌ماند؛ dedup ردیف‌های بدون URL در
                    # ingestion همین external_id را می‌سنجد (نه عنوان/متن مشترک).
                    if not ext:
                        ext = f"ind:{meta['indicator']}:{meta['period']}"
                items.append(RawItem(
                    title=title, url=col("url"), raw_text=body,
                    author=col("author"), raw_payload=json.dumps(row, ensure_ascii=False, default=str),
                    metadata={**meta, "external_id": ext},
                ))
            except Exception:  # noqa: BLE001 — یک سطر کل فایل را خراب نمی‌کند
                row_errors += 1
                continue
        return CsvResult(items, "ok", "", row_errors)
