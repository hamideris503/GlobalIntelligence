"""Article Classification (Phase 10; اصلاحات Phase 10 fix).

- طبقه‌بندی: topics, country, language, sentiment, stance, summary, entities
- محاسبه‌ی Importance Score ترکیبی (بند 22) با ۱۰ بُعد، **deterministic**
- novelty و historical_significance از سیستم (نه LLM)
- اعتبارسنجی JSON با jsonschema
- رد کردن نتیجه‌ی mock در حالت production
- وضعیت/تلاش/خطا و متادیتای اجرا در DB (Reproducibility)
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.ai.gateway import get_gateway
from backend.ai.prompts.classification import CLASSIFY_ARTICLE
from backend.ai.schemas.types import AIRequest, Message
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.database.models.article import Article
from domains.news.classifier_schema import (
    ALLOWED_ENTITY_TYPES,
    ALLOWED_TOPICS,
    CLASSIFY_SCHEMA,
    ClassificationResult,
    ImportanceInputs,
)

logger = get_logger(__name__)

MAX_ATTEMPTS = 3


def compute_novelty(db: Session, article: Article) -> float:
    """Novelty deterministic: چه مقدار از این خبر تازه/غیرتکراری است.

    بر پایه‌ی اندازه‌ی خوشه‌ی تکراری در ۷ روز گذشته. خوشه‌ی بزرگ → novelty کم.
    """
    since = datetime.now(UTC) - timedelta(days=7)
    cluster = article.duplicate_cluster
    if not cluster:
        return 1.0
    count = db.execute(
        select(func.count(Article.id)).where(
            Article.duplicate_cluster == cluster, Article.retrieved_at >= since
        )
    ).scalar_one()
    if count <= 1:
        return 1.0
    return max(0.0, 1.0 - (count - 1) * 0.2)


def compute_historical_significance(topic_count: int, entity_count: int) -> float:
    """تخمین ساده‌ی اهمیت تاریخی از غنای موضوع/موجودیت."""
    score = min(1.0, (topic_count * 0.15) + (entity_count * 0.1))
    return round(score, 3)


def compute_importance(inputs: ImportanceInputs) -> int:
    """محاسبه‌ی deterministic اهمیت از ۱ (بسیار مهم) تا ۱۰ (عادی)."""
    weights = {
        "impact": 0.18,
        "scope": 0.11,
        "probability": 0.07,
        "novelty": 0.11,
        "market_relevance": 0.13,
        "geopolitical_relevance": 0.09,
        "economic_relevance": 0.11,
        "time_sensitivity": 0.06,
        "strategic_relevance": 0.06,
        "historical_significance": 0.08,
    }
    values = inputs.as_dict()
    score = sum(values[k] * w for k, w in weights.items())
    score = max(0.0, min(1.0, score))
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
        self._settings = get_settings()

    async def classify_article(self, article: Article) -> ClassificationResult:
        text = f"{article.title or ''}\n{article.summary or ''}".strip()
        if not text:
            raise ValueError("empty article text")

        prompt = CLASSIFY_ARTICLE.render(
            topics=", ".join(sorted(ALLOWED_TOPICS)),
            entity_types=", ".join(sorted(ALLOWED_ENTITY_TYPES)),
            text=text[:4000],
        )
        request = AIRequest(
            messages=[
                Message.system("You output strict JSON compatible with the schema."),
                Message.user(prompt),
            ],
            role="fast_extraction",
            task="classify_article",
            temperature=0.1,
            json_schema=CLASSIFY_SCHEMA,
            metadata={"prompt_version": CLASSIFY_ARTICLE.version},
        )
        response = await self.gateway.structured_generate(request, CLASSIFY_SCHEMA)
        data = response.structured or _safe_json(response.text)
        if not isinstance(data, dict):
            raise ValueError("provider did not return a JSON object")

        # اعتبارسنجی با jsonschema
        _validate(data, CLASSIFY_SCHEMA)

        result = ClassificationResult.from_dict(data)
        result.prompt_version = response.prompt_version or CLASSIFY_ARTICLE.version
        result.provider = response.provider
        result.model = response.model
        result.is_mock = response.is_mock
        return result

    async def classify_pending(self, *, limit: int = 20) -> ClassifyOutcome:
        """مقالات pending با تلاش کمتر از حد مجاز را پردازش می‌کند."""
        stmt = (
            select(Article)
            .where(
                Article.classification_status == "pending",
                Article.classification_attempts < MAX_ATTEMPTS,
            )
            .order_by(Article.retrieved_at.desc().nullslast())
            .limit(limit)
        )
        articles = list(self.db.execute(stmt).scalars().all())
        outcome = ClassifyOutcome()
        for article in articles:
            article.classification_attempts = (article.classification_attempts or 0) + 1
            try:
                result = await self.classify_article(article)

                # در production، نتیجه‌ی mock ذخیره نمی‌شود (P0-1)
                if result.is_mock and not self._settings.mock_mode:
                    raise ValueError("mock result rejected in production mode")

                self._apply(article, result)
                article.classification_status = "done"
                article.classification_error = None
                outcome.classified += 1
            except Exception as exc:  # noqa: BLE001
                article.classification_error = f"{type(exc).__name__}: {exc}"[:2000]
                article.classification_status = (
                    "failed" if article.classification_attempts >= MAX_ATTEMPTS else "pending"
                )
                outcome.failed += 1
                outcome.errors.append(f"article={article.id}: {exc}")
                logger.warning("classify failed | article=%s err=%s", article.id, exc)
            self.db.commit()

        logger.info(
            "classify done | classified=%d failed=%d", outcome.classified, outcome.failed
        )
        return outcome

    def _apply(self, article: Article, result: ClassificationResult) -> None:
        # novelty و historical significance از سیستم
        result.importance_inputs.novelty = compute_novelty(self.db, article)
        result.importance_inputs.historical_significance = compute_historical_significance(
            len(result.topics), len(result.entities)
        )

        article.topics = json.dumps(result.topics, ensure_ascii=False)
        article.entities = json.dumps(
            [e.as_dict() for e in result.entities], ensure_ascii=False
        )
        article.sentiment = result.sentiment
        article.stance = result.stance
        article.country = result.country
        if result.summary:
            article.summary = result.summary[:2000]
        article.importance = compute_importance(result.importance_inputs)
        article.confidence = result.confidence

        # متادیتای اجرا برای Reproducibility
        meta = {
            "provider": result.provider,
            "model": result.model,
            "prompt_version": result.prompt_version,
            "is_mock": result.is_mock,
            "classified_at": datetime.now(UTC).isoformat(),
            "importance_inputs": result.importance_inputs.as_dict(),
            "response_hash": hashlib.sha256(
                json.dumps(result.topics, ensure_ascii=False).encode("utf-8")
            ).hexdigest()[:16],
        }
        article.classification_meta = json.dumps(meta, ensure_ascii=False)


def _validate(data: dict, schema: dict) -> None:
    try:
        import jsonschema

        jsonschema.validate(instance=data, schema=schema)
    except ImportError:  # pragma: no cover - اگر jsonschema نصب نبود
        return
    except Exception as exc:
        raise ValueError(f"schema validation failed: {exc}") from exc


def _safe_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:  # noqa: BLE001
                return None
        return None
