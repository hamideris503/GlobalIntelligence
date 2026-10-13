"""XML adapter — parser امن (defusedxml)، XXE/DTD بسته. RSS به مسیر RSS هدایت می‌شود."""
from __future__ import annotations

import json
from dataclasses import dataclass

import httpx
from defusedxml import ElementTree as DET

from domains.news.fetchers import RawItem
from source_bot.security import assert_public_host, validate_url


@dataclass
class XmlResult:
    items: list[RawItem]
    status: str
    detail: str = ""
    is_feed: bool = False


class XmlAdapter:
    name = "xml"

    def __init__(self, timeout: float = 20.0, max_bytes: int = 5_000_000) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes

    async def fetch(self, *, url: str | None, limit: int = 50) -> XmlResult:
        check = validate_url(url or "")
        if not check.ok:
            return XmlResult([], "http_error", f"refusing url: {check.reason}")
        assert url
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "GlobalIntelligenceBot/0.1",
                                                      "Accept": "application/xml, text/xml"})
                if resp.status_code in (401, 403):
                    return XmlResult([], "auth_required", f"http_{resp.status_code}")
                resp.raise_for_status()
                from urllib.parse import urlparse as _up

                final_host = (_up(str(getattr(resp, "url", url))).hostname or "").lower()
                assert_public_host(final_host)
                if len(resp.content) > self.max_bytes:
                    return XmlResult([], "http_error", "xml too big")
                content = resp.content
        except httpx.TimeoutException:
            return XmlResult([], "http_error", "timeout")
        except Exception as exc:  # noqa: BLE001
            return XmlResult([], "http_error", f"fetch_error:{type(exc).__name__}")
        return self.parse(content, limit=limit, source_url=url)

    def parse(self, content: bytes, *, limit: int, source_url: str = "") -> XmlResult:
        try:
            root = DET.fromstring(content)
        except Exception:  # noqa: BLE001
            return XmlResult([], "http_error", "xml_parse_error")
        tag = (root.tag or "").lower()
        if tag.endswith("rss") or tag.endswith("feed") or tag.endswith("rdf"):
            return XmlResult([], "is_feed", "rss detected: use rss adapter", is_feed=True)
        items: list[RawItem] = []

        def _text(el: object, names: tuple[str, ...]) -> str | None:
            try:
                for child in list(el):  # type: ignore[union-attr]
                    local = (child.tag or "").split("}")[-1].lower()
                    if local in names and (child.text or "").strip():
                        return child.text.strip()
            except Exception:  # noqa: BLE001
                pass
            return None

        records = list(root)[:limit]
        for rec in records:
            try:
                title = _text(rec, ("title", "name", "headline"))
                items.append(RawItem(
                    title=title, url=_text(rec, ("link", "url")),
                    raw_text=_text(rec, ("description", "summary", "content", "text")),
                    author=_text(rec, ("author", "creator")),
                    raw_payload=json.dumps({"tag": str(rec.tag)}, ensure_ascii=False),
                    metadata={"adapter": "xml", "source_url": source_url},
                ))
            except Exception:  # noqa: BLE001
                continue
        return XmlResult(items, "ok", "")
