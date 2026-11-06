"""Event Extraction (Phase 11).

مسیر: چند Article مرتبط (خوشه‌ی dedup) → یک Event واحد.

- گروه‌بندی بر اساس `duplicate_cluster` (خوشه‌ی dedup) یا `event_cluster`.
- استخراج فیلدهای Event با AI Gateway (structured JSON).
- اگر خوشه تک‌مقاله باشد، یک Event سبک از خود مقاله ساخته می‌شود (بدون AI).
- ID رویداد deterministic نیست اما اتصال مقاله↔رویداد ثبت می‌شود.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.ai.gateway import get_gateway
from backend.ai.schemas.types import AIRequest, Message
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.mock_mode import effective_mock_mode
from backend.database.models.article import Article
from backend.database.models.event import Event
from domains.events.prompts import EVENT_SCHEMA, EXTRACT_EVENT
from domains.events.type_rules import ONTOLOGY_TYPES, classify_event_type
from domains.geo.gazetteer import geocode_text

logger = get_logger(__name__)

MAX_ARTICLES_PER_EVENT = 8

# One extraction at a time per process: the dispatch consumer and the n8n
# /api/events/extract endpoint must not pick the same unlinked cluster twice.
_RUN_LOCK = asyncio.Lock()


@dataclass
class EventOutcome:
    events_created: int = 0
    articles_linked: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _iso_or_none(value: object) -> str | None:
    if not value:
        return None
    return str(value)


class EventExtractor:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.gateway = get_gateway()
        self._settings = get_settings()

    def _pending_clusters(
        self, *, limit: int, article_ids: list | None = None,
    ) -> list[tuple[str, list[Article]]]:
        """خوشه‌های مقالاتی که هنوز به هیچ Event وصل نشده‌اند.

        `article_ids` مسیر dispatch دوام‌دار است: فقط خوشه‌ی همین مقالات را
        برمی‌گرداند و اعضای همان خوشه را کامل نگه می‌دارد (Event تک‌مقاله‌ای
        نمی‌شود).
        """
        stmt = (
            select(Article)
            .where(Article.event_id.is_(None))
            .where(Article.classification_status == "done")
            .order_by(Article.retrieved_at.desc().nullslast())
            .limit(limit * MAX_ARTICLES_PER_EVENT)
        )
        if article_ids:
            targets = list(self.db.execute(
                select(Article).where(Article.id.in_(list(article_ids)))
            ).scalars().all())
            cluster_keys = {a.duplicate_cluster for a in targets if a.duplicate_cluster}
            single_ids = [a.id for a in targets if not a.duplicate_cluster]
            conditions = []
            if cluster_keys:
                conditions.append(Article.duplicate_cluster.in_(cluster_keys))
            if single_ids:
                conditions.append(Article.id.in_(single_ids))
            if not conditions:
                return []
            stmt = stmt.where(or_(*conditions))
        articles = list(self.db.execute(stmt).scalars().all())

        clusters: dict[str, list[Article]] = {}
        for a in articles:
            key = a.duplicate_cluster or f"single:{a.id}"
            clusters.setdefault(key, []).append(a)
        return list(clusters.items())[:limit]

    async def extract_event_from_cluster(self, articles: list[Article]) -> Event | None:
        """از یک خوشه‌ی مقالات، یک Event می‌سازد."""
        if not articles:
            return None

        # متن ترکیبی برای AI
        joined = "\n\n---\n\n".join(
            f"[{i+1}] {(a.title or '')}\n{a.summary or ''}"
            for i, a in enumerate(articles[:MAX_ARTICLES_PER_EVENT])
        )

        data: dict = {}
        confidence = None
        used_ai = False
        ai_failure_kind: str | None = None
        ai_failure_message: str | None = None
        ai_status_code: int | None = None
        try:
            if effective_mock_mode():
                raise RuntimeError("mock_mode_active: no real provider configured")
            prompt = EXTRACT_EVENT.render(articles=joined[:8000])
            request = AIRequest(
                messages=[
                    Message.system("You output strict JSON compatible with the schema."),
                    Message.user(prompt),
                ],
                role="deep_analysis",
                task="extract_event",
                temperature=0.1,
                json_schema=EVENT_SCHEMA,
                metadata={"prompt_version": EXTRACT_EVENT.version},
            )
            response = await self.gateway.structured_generate(request, EVENT_SCHEMA)
            if getattr(response, "is_mock", False):
                raise RuntimeError("mock_provider_response: provider returned mock")
            data = response.structured or _safe_json(response.text) or {}
            confidence = data.get("confidence")
            # Anti-hallucination validation (stage 3.7)
            issues: list[str] = []
            ai_type_raw = data.get("event_type")
            if ai_type_raw is not None:
                nt = str(ai_type_raw).strip().lower()
                if nt and nt not in ("unknown", "mock") and nt not in ONTOLOGY_TYPES:
                    issues.append("invalid_event_type")
                    data["event_type"] = None
                    ai_type_raw = None
            ai_loc = data.get("location")
            if ai_loc:
                # Anti-hallucination: AI location must literally appear in the
                # article/event text. Gazetteer is used for coordinates only.
                if _normalize_text(str(ai_loc)) not in _normalize_text(joined):
                    issues.append("location_not_in_text")
                    data["location"] = None
                    ai_loc = None
            # never trust AI coordinates
            data.pop("latitude", None)
            data.pop("longitude", None)
            data["validation_issues"] = issues
            # conflict with deterministic rules
            det_type, _, _, _ = classify_event_type(joined)
            ai_vs_rules = {
                "ai": ai_type_raw,
                "rules": det_type,
                "conflict": bool(ai_type_raw and det_type not in ("unknown",)
                                 and str(ai_type_raw).strip().lower() != det_type),
            }
            data["ai_vs_rules"] = ai_vs_rules
            if ai_vs_rules["conflict"]:
                data.setdefault("review_flags", []).append("ai_rules_conflict")
            used_ai = True
        except Exception as exc:  # noqa: BLE001
            ai_failure_kind = type(exc).__name__
            ai_failure_message = str(exc)[:300]
            # try to recover an HTTP status code from the exception chain
            for attr in ("status_code", "status"):
                val = getattr(exc, attr, None)
                if isinstance(val, int):
                    ai_status_code = val
                    break
            if ai_status_code is None:
                # search cause chain
                cur = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
                while cur is not None and ai_status_code is None:
                    for attr in ("status_code", "status"):
                        val = getattr(cur, attr, None)
                        if isinstance(val, int):
                            ai_status_code = val
                            break
                    cur = getattr(cur, "__cause__", None) or getattr(cur, "__context__", None)
            logger.warning(
                "event extraction failed, fallback to deterministic | err=%s kind=%s status=%s",
                exc, ai_failure_kind, ai_status_code,
            )

        # Event را بساز
        source_ids = sorted({str(a.document.source_id) for a in articles if a.document and a.document.source_id})
        ai_type = data.get("event_type")
        ai_location = data.get("location")
        type_reason = None
        type_score = None
        type_keywords: list[str] = []
        if (not ai_type or str(ai_type).strip().lower() in ("unknown", "mock")):
            etype, reason, score, matched = classify_event_type(joined)
            if etype != "unknown":
                ai_type = etype
            type_reason = reason
            type_score = score
            type_keywords = matched
        if not type_reason:
            type_reason = "ai_or_topic"
        event_type_value = ai_type or (articles[0].topics and _first_topic(articles[0])) or "unknown"

        geo = geocode_text(ai_location if ai_location else joined)
        if ai_location and geo["location_status"] == "unresolved":
            geo2 = geocode_text(joined)
            if geo2["location_status"].startswith("resolved"):
                geo = geo2
        location_value = ai_location or geo["location"]
        resolved = geo["location_status"].startswith("resolved")
        latitude_value = geo["latitude"] if resolved else None
        longitude_value = geo["longitude"] if resolved else None
        country_value = geo["country"] if resolved else None
        precision_value = geo["location_precision"] if resolved else None
        source_value = geo["location_source"] if resolved else None
        conf_value = geo["location_confidence"] if resolved else None
        location_reason = geo["location_reason"]

        event = Event(
            event_type=event_type_value,
            occurred_at=_parse_dt(data.get("occurred_at"))
            or min((a.published_at for a in articles if a.published_at), default=None),
            location=location_value,
            latitude=latitude_value,
            longitude=longitude_value,
            country=country_value,
            location_precision=precision_value,
            location_source=source_value,
            location_confidence=conf_value,
            actors=json.dumps(data.get("actors") or [], ensure_ascii=False),
            action=data.get("action") or (articles[0].title or None),
            expected=data.get("expected"),
            actual=data.get("actual"),
            surprise=data.get("surprise"),
            affected_assets=json.dumps(data.get("affected_assets") or [], ensure_ascii=False),
            affected_indicators=json.dumps(data.get("affected_indicators") or [], ensure_ascii=False),
            sources=json.dumps(source_ids, ensure_ascii=False),
            confidence=confidence if isinstance(confidence, (int, float)) else None,
            published_at=min((a.published_at for a in articles if a.published_at), default=None),
            retrieved_at=datetime.now(UTC),
            available_at=datetime.now(UTC),
            observed_at=datetime.now(UTC),
        )
        self.db.add(event)
        self.db.flush()

        # اتصال مقالات به رویداد
        cluster_id = str(event.id)
        for a in articles:
            a.event_id = event.id
            a.event_cluster = cluster_id

        event.event_metadata = json.dumps({
            "used_ai": used_ai,
            "article_count": len(articles),
            "type_reason": type_reason,
            "type_score": type_score,
            "type_keywords": type_keywords,
            "location_reason": location_reason,
            "ai_failure_kind": ai_failure_kind,
            "ai_failure_message": ai_failure_message,
            "ai_status_code": ai_status_code,
            "validation_issues": data.get("validation_issues", []),
            "ai_vs_rules": data.get("ai_vs_rules"),
            "review_flags": data.get("review_flags", []),
        }, ensure_ascii=False)
        return event

    async def run(self, *, limit: int = 50,
                  article_ids: list | None = None) -> EventOutcome:
        async with _RUN_LOCK:
            return await self._run(limit=limit, article_ids=article_ids)

    async def _run(self, *, limit: int = 50,
                   article_ids: list | None = None) -> EventOutcome:
        outcome = EventOutcome()
        clusters = self._pending_clusters(limit=limit, article_ids=article_ids)
        # Cluster policy (production): a cluster containing ANY explicit-mock
        # article is skipped so mock evidence cannot seed a new event. Unknown
        # provenance is processed (it is not proof of mock). Dev/test unchanged.
        mock_docs: set = set()
        if not effective_mock_mode() and clusters:
            from backend.database.models.document import mock_document_ids

            mock_docs = mock_document_ids(
                self.db,
                [a.document_id for _, arts in clusters for a in arts],
            )
        for _, articles in clusters:
            if mock_docs and any(a.document_id in mock_docs for a in articles):
                outcome.skipped += 1
                continue
            try:
                event = await self.extract_event_from_cluster(articles)
                if event is None:
                    continue
                outcome.events_created += 1
                outcome.articles_linked += len(articles)
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("event cluster failed | err=%s", exc)
            self.db.commit()
        logger.info(
            "event extraction done | events=%d linked=%d failed=%d skipped=%d",
            outcome.events_created, outcome.articles_linked, outcome.failed,
            outcome.skipped,
        )
        return outcome


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    import re
    return re.sub(r"\s+", " ", value.strip().lower())


def _first_topic(article: Article) -> str | None:
    try:
        topics = json.loads(article.topics or "[]")
        return topics[0] if topics else None
    except Exception:  # noqa: BLE001
        return None


def _parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except Exception:  # noqa: BLE001
        return None


def _safe_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:  # noqa: BLE001
                return None
        return None
