"""Schema و dataclassهای طبقه‌بندی (Phase 10)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# --- JSON Schema برای structured output ---
_IMPORTANCE_PROPS = {
    k: {"type": "number", "minimum": 0, "maximum": 1}
    for k in (
        "impact", "scope", "probability", "novelty", "market_relevance",
        "geopolitical_relevance", "economic_relevance", "time_sensitivity",
        "strategic_relevance", "historical_significance",
    )
}

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
        "sentiment": {"type": "number", "minimum": -1, "maximum": 1},
        "stance": {"type": "string"},
        "summary": {"type": "string"},
        "importance": {
            "type": "object",
            "properties": _IMPORTANCE_PROPS,
            "required": list(_IMPORTANCE_PROPS.keys()),
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["topics", "entities", "sentiment", "summary", "importance"],
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


ALLOWED_TOPICS = {
    "macroeconomics", "monetary_policy", "fiscal_policy", "inflation",
    "employment", "energy", "commodities", "markets", "equities",
    "fixed_income", "fx", "crypto", "geopolitics", "conflict", "sanctions",
    "trade", "politics", "society", "technology", "health", "climate",
}

ALLOWED_ENTITY_TYPES = {
    "person", "country", "company", "organization", "government",
    "central_bank", "asset", "commodity", "currency", "industry",
    "political_party", "indicator", "other",
}


@dataclass
class Entity:
    name: str
    type: str

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "type": self.type}


@dataclass
class ImportanceInputs:
    """ابعاد اهمیت، همه در بازه‌ی 0..1 (1 = مهم‌تر).

    novelty و historical_significance deterministic محاسبه می‌شوند (نه از LLM).
    """

    impact: float = 0.0
    scope: float = 0.0
    probability: float = 0.5
    novelty: float = 0.0
    market_relevance: float = 0.0
    geopolitical_relevance: float = 0.0
    economic_relevance: float = 0.0
    time_sensitivity: float = 0.0
    strategic_relevance: float = 0.0
    historical_significance: float = 0.0

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
            "historical_significance": self.historical_significance,
        }


def _clamp(v: Any, lo: float, hi: float, default: float) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, f))


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
    is_mock: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClassificationResult:
        # topics: فقط از لیست مجاز، حداکثر ۱۰
        topics_raw = data.get("topics") or []
        if isinstance(topics_raw, str):
            topics_raw = [topics_raw]
        topics = [str(t).lower() for t in topics_raw if str(t).lower() in ALLOWED_TOPICS][:10]

        entities: list[Entity] = []
        seen: set[str] = set()
        for e in data.get("entities") or []:
            if isinstance(e, dict) and e.get("name"):
                name = str(e["name"]).strip()
                etype = str(e.get("type", "other")).lower()
                if etype not in ALLOWED_ENTITY_TYPES:
                    etype = "other"
                key = name.lower()
                if name and key not in seen:
                    seen.add(key)
                    entities.append(Entity(name=name, type=etype))

        imp_raw = data.get("importance") or {}
        imp = ImportanceInputs(
            impact=_clamp(imp_raw.get("impact"), 0, 1, 0.0),
            scope=_clamp(imp_raw.get("scope"), 0, 1, 0.0),
            probability=_clamp(imp_raw.get("probability"), 0, 1, 0.5),
            novelty=_clamp(imp_raw.get("novelty"), 0, 1, 0.0),
            market_relevance=_clamp(imp_raw.get("market_relevance"), 0, 1, 0.0),
            geopolitical_relevance=_clamp(imp_raw.get("geopolitical_relevance"), 0, 1, 0.0),
            economic_relevance=_clamp(imp_raw.get("economic_relevance"), 0, 1, 0.0),
            time_sensitivity=_clamp(imp_raw.get("time_sensitivity"), 0, 1, 0.0),
            strategic_relevance=_clamp(imp_raw.get("strategic_relevance"), 0, 1, 0.0),
            historical_significance=_clamp(imp_raw.get("historical_significance"), 0, 1, 0.0),
        )

        country = data.get("country")
        if isinstance(country, str):
            country = country.strip().upper()[:2] or None
        else:
            country = None

        sentiment = data.get("sentiment")
        sentiment = _clamp(sentiment, -1, 1, 0.0) if sentiment is not None else None

        confidence = data.get("confidence")
        confidence = _clamp(confidence, 0, 1, 0.0) if confidence is not None else None

        return cls(
            topics=topics,
            country=country,
            entities=entities,
            sentiment=sentiment,
            stance=(data.get("stance") or None),
            summary=(data.get("summary") or None),
            importance_inputs=imp,
            confidence=confidence,
        )
