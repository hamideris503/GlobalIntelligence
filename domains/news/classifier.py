"""Article Classification (Phase 10).

- طبقه‌بندی: topics, country, language, sentiment, stance, summary
- استخراج entity
- محاسبه‌ی Importance Score ترکیبی (بند 22) — نه فقط نظر LLM

Importance Score:
    1 = بسیار مهم ... 10 = عادی
ترکیب deterministic از ابعاد: impact, scope, probability, novelty,
market/geopolitical/economic relevance, time sensitivity, strategic relevance.

از AI برای طبقه‌بندی/استخراج استفاده می‌شود، اما محاسبه‌ی importance
deterministic است (بند 14 و 22).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.ai.gateway import get_gateway
from backend.ai.prompts.classification import CLASSIFY_ARTICLE
from backend.ai.schemas.types import AIRequest, Message
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.database.models.article import Article
from domains.news.classifier_schema import (
    CLASSIFY_SCHEMA,
    ClassificationResult,
    ImportanceInputs,
)

logger = get_logger(__name__)

# دسته‌بندی موضوعی پایه
TOPICS = [
    "macroeconomics", "monetary_policy", "fiscal_policy", "inflation",
    "employment", "energy", "commodities", "markets", "equities",
    "fixed_income", "fx", "crypto", "geopolitics", "conflict", "sanctions",
    "trade", "politics", "society", "technology", "health", "climate",
]
ENTITY_TYPES = [
    "person", "country", "company", "organization", "government",
    "central_bank", "asset", "commodity", "currency", "industry",
    "political_party", "indicator",
]


def compute_importance(inputs: ImportanceInputs) -> int:
    """محاسبه‌ی deterministic اهمیت از ۱ (بسیار مهم) تا ۱۰ (عادی).

    میانگین وزنی ابعاد، سپس نگاشت به بازه‌ی ۱..۱۰.
    """
    weights = {
        "impact": 0.20,
        "scope": 0.12,
        "probability": 0.10,
        "novelty": 0.12,
        "market_relevance": 0.14,
        "geopolitical_relevance": 0.10,
        "economic_relevance": 0.12,
        "time_sensitivity": 0.06,
        "strategic_relevance": 0.04,
    }
    values = inputs.as_dict()
    score = sum(values[k] * w for k, w in weights.items())  # 0..1، 1 = مهم‌ترین
    score = max(0.0, min(1.0, score))
    # نگاشت خطی معکوس: score=1 → 1 ، score=0 → 10
    importance = round(1 + (1 - score) * 9)
    return int(max(1, min(10, importance)))


@dataclass
class ClassifyOutcome:
    classified: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


class ArticleClassifier:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.gateway = get_gateway()

    async def classify_article(self, article: Article) -> ClassificationResult | None:
        text = article.summary or article.title or ""
        if not text.strip():
            return None

        prompt = CLASSIFY_ARTICLE.render(
            topics=", ".join(TOPICS),
            countries="US, GB, EU, CN, RU, IR, SA, ...",
            title=article.title or "",
            text=text[:4000],
        )
        request = AIRequest(
            messages=[Message.system("You output strict JSON."), Message.user(prompt)],
            role="fast_extraction",
            task="classify_article",
            temperature=0.1,
            json_schema=CLASSIFY_SCHEMA,
            metadata={"prompt_version": CLASSIFY_ARTICLE.version},
        )
        response = await self.gateway.structured_generate(request, CLASSIFY_SCHEMA)
        data = response.structured or _safe_json(response.text)
        if not isinstance(data, dict):
            return None

        result = ClassificationResult.from_dict(data)
        result.prompt_version = response.prompt_version
        result.provider = response.provider
        result.model = response.model
        return result

    async def classify_pending(self, *, limit: int = 20) -> ClassifyOutcome:
        """مقالاتی که هنوز طبقه‌بندی نشده‌اند (topics خالی) را پردازش می‌کند."""
        stmt = (
            select(Article)
            .where(Article.topics.is_(None))
            .order_by(Article.retrieved_at.desc().nullslast())
            .limit(limit)
        )
        articles = list(self.db.execute(stmt).scalars().all())
        outcome = ClassifyOutcome()
        for article in articles:
            try:
                result = await self.classify_article(article)
                if result is None:
                    outcome.failed += 1
                    continue
                self._apply(article, result)
                outcome.classified += 1
            except Exception as exc:  # noqa: BLE001
                outcome.failed += 1
                outcome.errors.append(f"{type(exc).__name__}: {exc}")
                logger.warning("classify failed | article=%s err=%s", article.id, exc)
        self.db.commit()
        logger.info(
            "classify done | classified=%d failed=%d", outcome.classified, outcome.failed
        )
        return outcome

    def _apply(self, article: Article, result: ClassificationResult) -> None:
        article.topics = json.dumps(result.topics, ensure_ascii=False)
        article.entities = json.dumps(
            [e.as_dict() for e in result.entities], ensure_ascii=False
        )
        article.sentiment = result.sentiment
        article.stance = result.stance
        if result.summary:
            article.summary = result.summary[:1000]
        if result.country and not article.language:
            pass
        article.importance = compute_importance(result.importance_inputs)
        article.confidence = result.confidence


def _safe_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        # تلاش برای یافتن اولین شیء JSON
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:  # noqa: BLE001
                return None
        return None
