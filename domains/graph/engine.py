"""Knowledge Graph Engine (Phase 15).

مسیر: Article/Event → Entity (+ canonical resolution) → EntityRelationship.

- Entity resolution: نام نرمال‌شده به‌عنوان `canonical_name`؛ موجودیت موجود
  (هم‌نوع) به‌روزرسانی و نام‌های دیگرش به `aliases` اضافه می‌شود.
- Relationships: استخراج با AI (structured JSON) از متن رویداد و موجودیت‌هایش؛
  در نبود AI، fallback هم‌رویدادی (`affects`) بین بازیگران/موجودیت‌ها.
- idempotency: هر Event یک‌بار پردازش می‌شود (`graph_extracted`).

Deterministic در بخش resolution؛ استخراج رابطه با AI Gateway.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ai.gateway import get_gateway
from backend.ai.schemas.types import AIRequest, Message
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.database.enums import EntityType, RelationType
from backend.database.models.entity import Entity, EntityRelationship
from backend.database.models.event import Event
from domains.graph.prompts import EXTRACT_RELATIONS, RELATIONS_SCHEMA

logger = get_logger(__name__)

MAX_RELATIONSHIPS = 12
MAX_TEXT_CHARS = 6000

ALLOWED_ENTITY_TYPES = {t.value for t in EntityType}
ALLOWED_RELATIONS = {r.value for r in RelationType}


@dataclass
class GraphOutcome:
    events_processed: int = 0
    entities_created: int = 0
    entities_updated: int = 0
    relationships_created: int = 0
    rejected: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "events_processed": self.events_processed,
            "entities_created": self.entities_created,
            "entities_updated": self.entities_updated,
            "relationships_created": self.relationships_created,
            "rejected": self.rejected,
            "failed": self.failed,
            "errors": self.errors,
        }


def normalize_name(name: str) -> str:
    """نام canonical برای Entity resolution (deterministic)."""
    return " ".join(name.strip().split()).casefold()


def _clamp01(value: object, default: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _load_meta(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return {}


def _parse_list(raw: str | None) -> list:
    if not raw:
        return []
    try:
        out = json.loads(raw)
        return out if isinstance(out, list) else []
    except Exception:  # noqa: BLE001
        return []


class KnowledgeGraphEngine:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.gateway = get_gateway()
        self._settings = get_settings()

    # --- Entity resolution ---
    def upsert_entity(
        self, name: str, etype: str, *, outcome: GraphOutcome, alias: str | None = None
    ) -> tuple[Entity | None, bool]:
        """موجودیت را می‌سازد/به‌روزرسانی می‌کند. خروجی: (entity, created).

        هویت موجودیت بر اساس **نام** (canonical_name) است؛ اگر همان نام با نوع
        `other` وجود داشته باشد و نوع مشخص‌تری برسد، ارتقا می‌یابد.
        """
        display = name.strip()
        if not display:
            return None, False
        if etype not in ALLOWED_ENTITY_TYPES:
            etype = EntityType.other.value
        canonical = normalize_name(display)

        entity = self.db.execute(
            select(Entity).where(Entity.canonical_name == canonical)
        ).scalar_one_or_none()

        if entity is None:
            entity = Entity(
                type=etype,
                canonical_name=canonical,
                display_name=display,
                aliases=json.dumps([], ensure_ascii=False),
            )
            self.db.add(entity)
            self.db.flush()
            outcome.entities_created += 1
            created = True
        else:
            created = False
            # ارتقای نوع از other به نوع مشخص
            if entity.type == EntityType.other.value and etype != EntityType.other.value:
                entity.type = etype
            if entity.display_name is None:
                entity.display_name = display
            outcome.entities_updated += 1

        candidate_aliases = json.loads(entity.aliases or "[]")
        for a in filter(None, [alias, display]):
            if a and a != entity.display_name and a not in candidate_aliases:
                candidate_aliases.append(a)
        entity.aliases = json.dumps(candidate_aliases, ensure_ascii=False)
        return entity, created

    # --- Relationships ---
    def _event_text(self, event: Event) -> str:
        parts = []
        if event.action:
            parts.append(event.action)
        for article in event.articles[:8]:
            if article.title:
                parts.append(article.title)
            if article.summary:
                parts.append(article.summary)
        return "\n".join(parts)[:MAX_TEXT_CHARS]

    def _link(self, from_e: Entity, to_e: Entity, relation: str, weight: float, confidence: float, event: Event) -> bool:
        """یک یال می‌سازد/به‌روز می‌کند (idempotent روی جفت+رابطه)."""
        existing = self.db.execute(
            select(EntityRelationship).where(
                EntityRelationship.from_entity_id == from_e.id,
                EntityRelationship.to_entity_id == to_e.id,
                EntityRelationship.relation == relation,
            )
        ).scalar_one_or_none()
        if existing is not None:
            # تقویت وزن/اعتماد و افزودن شاهد
            existing.weight = max(existing.weight or 0.0, weight)
            existing.confidence = max(existing.confidence or 0.0, confidence)
            ev = json.loads(existing.evidence or "[]")
            if str(event.id) not in ev:
                ev.append(str(event.id))
            existing.evidence = json.dumps(ev, ensure_ascii=False)
            return False
        rel = EntityRelationship(
            from_entity_id=from_e.id,
            to_entity_id=to_e.id,
            relation=relation,
            weight=weight,
            confidence=confidence,
            evidence=json.dumps([str(event.id)], ensure_ascii=False),
        )
        self.db.add(rel)
        self.db.flush()
        return True

    async def extract_for_event(self, event: Event) -> GraphOutcome:
        outcome = GraphOutcome()
        entities_raw = _parse_list(event.actors)

        # 1) Entityهای رویداد (از actors + مقالات طبقه‌بندی‌شده)
        resolved: dict[str, Entity] = {}
        for name in entities_raw:
            if isinstance(name, str) and name.strip():
                ent, _ = self.upsert_entity(name.strip(), EntityType.other.value, outcome=outcome)
                if ent is not None:
                    resolved[normalize_name(name)] = ent

        for article in event.articles:
            for e in _parse_list(article.entities):
                if isinstance(e, dict) and e.get("name"):
                    name = str(e["name"]).strip()
                    etype = str(e.get("type") or "other").lower()
                    ent, _ = self.upsert_entity(name, etype, outcome=outcome)
                    if ent is not None:
                        resolved[normalize_name(name)] = ent

        # 2) استخراج رابطه با AI
        rel_data: list[dict] = []
        used_ai = False
        text = self._event_text(event)
        if len(resolved) >= 2 and text.strip():
            entities_str = "\n".join(
                f"- {e.display_name} | {e.type}" for e in resolved.values()
            )
            try:
                prompt = EXTRACT_RELATIONS.render(
                    entities=entities_str,
                    data=text,
                    relations=", ".join(sorted(ALLOWED_RELATIONS)),
                    max_items=MAX_RELATIONSHIPS,
                )
                request = AIRequest(
                    messages=[
                        Message.system("You output strict JSON compatible with the schema."),
                        Message.user(prompt),
                    ],
                    role="deep_analysis",
                    task="extract_relations",
                    temperature=0.1,
                    json_schema=RELATIONS_SCHEMA,
                    metadata={"prompt_version": EXTRACT_RELATIONS.version},
                )
                response = await self.gateway.structured_generate(request, RELATIONS_SCHEMA)
                if response.is_mock and not self._settings.mock_mode:
                    raise ValueError("mock relations rejected in production mode")
                parsed = response.structured or _safe_json(response.text) or {}
                rel_data = parsed.get("relationships") or []
                used_ai = bool(rel_data)
            except Exception as exc:  # noqa: BLE001
                logger.warning("relation extraction failed | event=%s err=%s", event.id, exc)

        created = 0
        rejected = 0
        seen: set[tuple[str, str, str]] = set()
        for item in rel_data[:MAX_RELATIONSHIPS]:
            if not isinstance(item, dict):
                rejected += 1
                continue
            f_key = normalize_name(str(item.get("from") or ""))
            t_key = normalize_name(str(item.get("to") or ""))
            relation = str(item.get("relation") or "").lower()
            if f_key not in resolved or t_key not in resolved:
                rejected += 1
                logger.warning("relation rejected | event=%s unknown entity", event.id)
                continue
            if relation not in ALLOWED_RELATIONS or f_key == t_key:
                rejected += 1
                logger.warning("relation rejected | event=%s relation=%r", event.id, relation)
                continue
            key = (f_key, t_key, relation)
            if key in seen:
                continue
            seen.add(key)
            if self._link(
                resolved[f_key],
                resolved[t_key],
                relation,
                _clamp01(item.get("weight"), 0.5),
                _clamp01(item.get("confidence"), 0.5),
                event,
            ):
                created += 1

        # 3) fallback: اگر هیچ رابطه‌ی معتبری ساخته نشد، هم‌رویدادی‌ها را با affects وصل کن
        if created == 0 and len(resolved) >= 2:
            items = list(resolved.items())
            for i in range(len(items)):
                for j in range(i + 1, min(i + 4, len(items))):
                    f_key, f_e = items[i]
                    t_key, t_e = items[j]
                    if f_key == t_key:
                        continue
                    if self._link(
                        f_e, t_e, RelationType.affects.value, 0.3, 0.3, event
                    ):
                        created += 1

        event.graph_extracted = True
        if used_ai:
            meta = _load_meta(event.event_metadata)
            meta["graph_ai"] = True
            meta["relations_prompt_version"] = EXTRACT_RELATIONS.version
            event.event_metadata = json.dumps(meta, ensure_ascii=False)

        outcome.relationships_created = created
        outcome.rejected += rejected
        self.db.flush()
        return outcome

    async def run(self, *, limit: int = 50) -> GraphOutcome:
        total = GraphOutcome()
        stmt = (
            select(Event)
            .where(Event.graph_extracted.is_(False))
            .order_by(Event.created_at.desc())
            .limit(limit)
        )
        events = list(self.db.execute(stmt).scalars().all())
        for event in events:
            try:
                res = await self.extract_for_event(event)
                total.events_processed += 1
                total.entities_created += res.entities_created
                total.entities_updated += res.entities_updated
                total.relationships_created += res.relationships_created
                total.rejected += res.rejected
            except Exception as exc:  # noqa: BLE001
                total.failed += 1
                total.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("graph event failed | event=%s err=%s", event.id, exc)
            self.db.commit()
        logger.info("knowledge-graph done | %s", total.as_dict())
        return total


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
