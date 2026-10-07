"""Schema و dataclassهای طبقه‌بندی (Phase 10)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --- JSON Schema برای structured output ---
CLASSIFY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "topics": {"type": "array", "items": {"type": "string"}},
        "country": {"type": ["string", "null"]},
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                },
                "required": ["name", "type"],
            },
        },
        "sentiment": {"type": "number"},
        "stance": {"type": "string"},
        "summary": {"type": "string"},
        "importance": {
            "type": "object",
            "properties": {
                "impact": {"type": "number"},
                "scope": {"type": "number"},
                "probability": {"type": "number"},
                "novelty": {"type": "number"},
                "market_relevance": {"type": "number"},
                "geopolitical_relevance": {"type": "number"},
                "economic_relevance": {"type": "number"},
                "time_sensitivity": {"type": "number"},
                "strategic_relevance": {"type": "number"},
            },
        },
        "confidence": {"type": "number"},
    },
    "required": ["topics", "entities", "sentiment", "summary"],
}

EXTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "type": {"type": "string"}},
                "required": ["name", "type"],
            },
        }
    },
    "required": ["entities"],
}


@dataclass
class Entity:
    name: str
    type: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "type": self.type}


@dataclass
class ImportanceInputs:
    """ابعاد اهمیت، همه در بازه‌ی 0..1 (1 = مهم‌تر)."""

    impact: float = 0.0
    scope: float = 0.0
    probability: float = 0.5
    novelty: float = 0.0
    market_relevance: float = 0.0
    geopolitical_relevance: float = 0.0
    economic_relevance: float = 0.0
    time_sensitivity: float = 0.0
    strategic_relevance: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "impact": self.impact,
            "scope": self.scope,
            "probability": self.probability,
            "novelty": self.novelty,
            "market_relevance": self.market_relevance,
            "geopolitical_relevance": self.geopolitical_relevance,
            "economic_relevance": self.economic_relevance,
            "time_sensitivity": self.time_sensitivity,
            "strategic_relevance": self.strategic_relevance,
        }


def _clamp01(v: Any, default: float = 0.0) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, f))


@dataclass
class ClassificationResult:
    topics: list[str] = field(default_factory=list)
    country: str | None = None
    entities: list[Entity] = field(default_factory=list)
    sentiment: float | None = None
    stance: str | None = None
    summary: str | None = None
    importance_inputs: ImportanceInputs = field(default_factory=ImportanceInputs)
    confidence: float | None = None
    # متادیتای اجرا (Reproducibility)
    prompt_version: str | None = None
    provider: str | None = None
    model: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClassificationResult":
        topics = data.get("topics") or []
        if isinstance(topics, str):
            topics = [topics]
        topics = [str(t) for t in topics if t][:10]

        entities = []
        for e in data.get("entities") or []:
            if isinstance(e, dict) and e.get("name"):
                entities.append(Entity(name=str(e["name"]), type=str(e.get("type", "other"))))

        imp_raw = data.get("importance") or {}
        imp = ImportanceInputs(
            impact=_clamp01(imp_raw.get("impact")),
            scope=_clamp01(imp_raw.get("scope")),
            probability=_clamp01(imp_raw.get("probability"), 0.5),
            novelty=_clamp01(imp_raw.get("novelty")),
            market_relevance=_clamp01(imp_raw.get("market_relevance")),
            geopolitical_relevance=_clamp01(imp_raw.get("geopolitical_relevance")),
            economic_relevance=_clamp01(imp_raw.get("economic_relevance")),
            time_sensitivity=_clamp01(imp_raw.get("time_sensitivity")),
            strategic_relevance=_clamp01(imp_raw.get("strategic_relevance")),
        )

        return cls(
            topics=topics,
            country=data.get("country"),
            entities=entities,
            sentiment=data.get("sentiment"),
            stance=data.get("stance"),
            summary=data.get("summary"),
            importance_inputs=imp,
            confidence=data.get("confidence"),
        )
