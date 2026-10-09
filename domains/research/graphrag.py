"""GraphRAG-lite — بازیابی زیرگراف k-hop و زمینه‌سازی (Phase 52).

ایده (v1, مستند):
- موجودیت‌های پرس‌وجو با تطبیق نام نرمال‌شده resolve می‌شوند (همان قرارداد Phase 15).
- همسایگی k-hop روی entity_relationships (جهت‌دار، هر دو سو) با سقف تعداد.
- رتبه‌بندی یال‌ها با weight (تهی → 0.5 خنثی، نه صفر) و گره‌ها با درجه‌ی وزنی.
- خروجی ساخت‌یافته (گره‌ها/یال‌ها/متن) برای مصرف LLM یا انسان.
- سنتز متنی اختیاری با AI Gateway؛ در MOCK_MODE، خلاصه‌ی استخراجی
  (نه توهم) با پرچم صریح برمی‌گردد.

ارزیابی تکنیک‌های دیگر در ADR-0061 (به تعویق افتاد با دلیل).
بدون migration؛ فقط خواندنی (+ فراخوانی اختیاری AI).
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ai.gateway import get_gateway
from backend.ai.schemas.types import AIRequest, Message
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.database.models.entity import Entity, EntityRelationship

logger = get_logger(__name__)

DEFAULT_HOPS = 2
DEFAULT_LIMIT = 50
NEUTRAL_WEIGHT = 0.5


@dataclass
class GraphContext:
    seed_entities: list[dict] = field(default_factory=list)
    nodes: list[dict] = field(default_factory=list)
    edges: list[dict] = field(default_factory=list)
    hops: int = DEFAULT_HOPS
    truncated: bool = False
    synthesis: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "seed_entities": self.seed_entities,
            "nodes": self.nodes,
            "edges": self.edges,
            "hops": self.hops,
            "truncated": self.truncated,
            "synthesis": self.synthesis,
        }

    def as_text(self) -> str:
        lines = []
        for e in self.edges:
            lines.append(
                f"{e['from']} --{e['relation']}--> {e['to']} "
                f"(w={e.get('weight')})"
            )
        return "\n".join(lines)


def normalize_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


SYNTH_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_relations": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["summary", "key_relations"],
}


class GraphRAGService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.gateway = get_gateway()
        self._settings = get_settings()

    def _resolve(self, names: list[str]) -> list[Entity]:
        out: list[Entity] = []
        for raw in names:
            key = normalize_name(raw)
            if not key:
                continue
            ent = self.db.execute(
                select(Entity).where(Entity.canonical_name == key)
            ).scalar_one_or_none()
            if ent is None:
                ent = self.db.execute(
                    select(Entity).where(Entity.display_name == raw.strip())
                ).scalar_one_or_none()
            if ent is not None and ent.id not in {e.id for e in out}:
                out.append(ent)
        return out

    def _adjacency(self) -> dict[object, list[EntityRelationship]]:
        adj: dict[object, list[EntityRelationship]] = defaultdict(list)
        for rel in self.db.execute(select(EntityRelationship)).scalars().all():
            adj[rel.from_entity_id].append(rel)
            adj[rel.to_entity_id].append(rel)
        return adj

    def retrieve(
        self,
        *,
        entity_names: list[str],
        hops: int = DEFAULT_HOPS,
        limit: int = DEFAULT_LIMIT,
    ) -> GraphContext:
        seeds = self._resolve(entity_names)
        ctx = GraphContext(hops=max(0, hops))
        if not seeds:
            return ctx
        ctx.seed_entities = [
            {"id": str(e.id), "name": e.display_name, "type": e.type} for e in seeds
        ]

        adj = self._adjacency()
        seen_nodes: dict[object, Entity] = {e.id: e for e in seeds}
        seen_edges: dict[object, EntityRelationship] = {}
        queue: deque[tuple[object, int]] = deque((e.id, 0) for e in seeds)
        visited: set[object] = set()

        by_id: dict[object, Entity] = dict(seen_nodes)
        while queue and len(seen_edges) < limit:
            node_id, depth = queue.popleft()
            if node_id in visited or depth >= ctx.hops:
                continue
            visited.add(node_id)
            for rel in adj.get(node_id, []):
                if rel.id in seen_edges:
                    continue
                if len(seen_edges) >= limit:
                    break
                seen_edges[rel.id] = rel
                for eid in (rel.from_entity_id, rel.to_entity_id):
                    if eid not in by_id:
                        ent = self.db.get(Entity, eid)
                        if ent is not None:
                            by_id[eid] = ent
                            seen_nodes[eid] = ent
                    if eid not in visited and depth + 1 < ctx.hops:
                        queue.append((eid, depth + 1))
        ctx.truncated = len(seen_edges) >= limit

        def w(rel: EntityRelationship) -> float:
            return rel.weight if rel.weight is not None else NEUTRAL_WEIGHT

        degree: dict[object, float] = defaultdict(float)
        for rel in seen_edges.values():
            degree[rel.from_entity_id] += w(rel)
            degree[rel.to_entity_id] += w(rel)

        ctx.nodes = [
            {
                "id": str(e.id),
                "name": e.display_name,
                "type": e.type,
                "weighted_degree": round(degree.get(e.id, 0.0), 4),
            }
            for e in seen_nodes.values()
        ]
        ctx.nodes.sort(key=lambda n: n["weighted_degree"], reverse=True)
        edges = []
        for rel in seen_edges.values():
            f = by_id.get(rel.from_entity_id)
            t = by_id.get(rel.to_entity_id)
            edges.append(
                {
                    "from": f.display_name if f else str(rel.from_entity_id),
                    "to": t.display_name if t else str(rel.to_entity_id),
                    "relation": rel.relation,
                    "weight": w(rel),
                    "confidence": rel.confidence,
                }
            )
        edges.sort(key=lambda e: e["weight"], reverse=True)
        ctx.edges = edges
        return ctx

    async def synthesize(self, ctx: GraphContext) -> dict:
        """سنتز متنی اختیاری؛ در mock خلاصه‌ی استخراجی صادقانه."""
        if not ctx.edges:
            return {"summary": "", "key_relations": [], "mode": "empty"}
        if self._settings.mock_mode:
            top = [f"{e['from']} {e['relation']} {e['to']}" for e in ctx.edges[:5]]
            return {
                "summary": f"extractive: {len(ctx.nodes)} entities, "
                f"{len(ctx.edges)} relations (mock mode, no LLM)",
                "key_relations": top,
                "mode": "extractive",
            }
        request = AIRequest(
            messages=[
                Message.system("You output strict JSON compatible with the schema."),
                Message.user(
                    "Summarize this knowledge-graph context in 3 sentences and "
                    f"list key relations:\n{ctx.as_text()[:4000]}"
                ),
            ],
            role="deep_analysis",
            task="graphrag_synthesize",
            temperature=0.2,
            json_schema=SYNTH_SCHEMA,
            metadata={"prompt_version": "graphrag_v1"},
        )
        try:
            response = await self.gateway.structured_generate(request, SYNTH_SCHEMA)
            data = response.structured or {}
            return {
                "summary": data.get("summary", ""),
                "key_relations": data.get("key_relations", [])[:10],
                "mode": "llm",
                "provider": response.provider,
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("graphrag synthesize failed: %s", exc)
            return {"summary": "", "key_relations": [], "mode": "failed"}
