"""Phase 10 validation: realistic classification (golden set).

با یک Provider جعلی واقع‌گرایانه (نه mock ساده) بررسی می‌کنیم:
- importance در بازه‌های مختلف می‌افتد (نه همه ۱۰)
- country ذخیره می‌شود
- متادیتای اجرا (provider/model/prompt_version) ذخیره می‌شود
"""
from __future__ import annotations

import asyncio
import json

from backend.database.models.article import Article
from backend.database.models.document import Document
from backend.database.models.source import Source
from domains.news.classifier import ArticleClassifier
from tests.conftest import TestingSession

# سه خبر با اهمیت متفاوت
GOLDEN = [
    {
        "title": "Central bank raises interest rate by 200bps in emergency move",
        "summary": "The central bank surprised markets with an emergency 200bps rate hike.",
        "importance": {
            "impact": 0.95, "scope": 0.85, "probability": 0.5, "novelty": 0.9,
            "market_relevance": 0.95, "geopolitical_relevance": 0.2,
            "economic_relevance": 0.95, "time_sensitivity": 0.9, "strategic_relevance": 0.7,
        },
        "country": "US",
        "expected_bucket": (1, 3),
    },
    {
        "title": "Monthly regional housing report published",
        "summary": "Routine monthly housing statistics were released.",
        "importance": {
            "impact": 0.1, "scope": 0.2, "probability": 0.5, "novelty": 0.1,
            "market_relevance": 0.1, "geopolitical_relevance": 0.0,
            "economic_relevance": 0.3, "time_sensitivity": 0.1, "strategic_relevance": 0.1,
        },
        "country": "GB",
        "expected_bucket": (7, 10),
    },
]


class _GoldenProvider:
    """Provider جعلی که پاسخ واقع‌گرایانه بر اساس ورودی برمی‌گرداند."""

    name = "golden"

    def __init__(self, mapping) -> None:
        self._mapping = mapping

    async def generate(self, request):  # noqa: ANN001
        from backend.ai.schemas.types import AIResponse

        text = request.messages[-1].content
        payload = None
        for key, data in self._mapping.items():
            if key in text:
                payload = data
                break
        if payload is None:
            payload = self._mapping[list(self._mapping)[0]]
        body = {
            "topics": ["monetary_policy"],
            "country": payload["country"],
            "entities": [{"name": "Central Bank", "type": "central_bank"}],
            "sentiment": 0.0,
            "stance": "neutral",
            "summary": payload["title"],
            "importance": payload["importance"],
            "confidence": 0.9,
        }
        return AIResponse(
            text=json.dumps(body), provider=self.name, model="golden-1",
            structured=body, is_mock=False, prompt_version="v2",
        )

    async def health(self):  # noqa: ANN001
        from backend.ai.schemas.types import ProviderHealth

        return ProviderHealth(provider=self.name, healthy=True)


def _seed_articles() -> None:
    session = TestingSession()
    try:
        src = Source(name="Golden", domain="g.local", type="rss", active=True)
        session.add(src)
        session.flush()
        for item in GOLDEN:
            doc = Document(source_id=src.id, title=item["title"], raw_text=item["summary"])
            session.add(doc)
            session.flush()
            session.add(
                Article(document_id=doc.id, title=item["title"], summary=item["summary"])
            )
        session.commit()
    finally:
        session.close()


def test_golden_classification_importance_and_country(monkeypatch) -> None:
    _seed_articles()
    session = TestingSession()
    try:
        mapping = {item["title"][:30]: item for item in GOLDEN}
        classifier = ArticleClassifier(session)
        classifier.gateway._providers["golden"] = _GoldenProvider(mapping)
        classifier.gateway._settings.mock_mode = False
        classifier.gateway._settings.ai_default_provider = "golden"

        outcome = asyncio.run(classifier.classify_pending(limit=10))
        assert outcome.classified == 2

        arts = session.query(Article).order_by(Article.importance).all()
        importances = [a.importance for a in arts]
        # importance نباید همه ۱۰ باشد و باید تنوع داشته باشد
        assert len(set(importances)) >= 2
        assert min(importances) <= 4  # خبر مهم
        assert max(importances) >= 6  # خبر عادی

        # country ذخیره شده
        countries = {a.country for a in arts}
        assert "US" in countries

        # متادیتای اجرا ذخیره شده (Reproducibility)
        for a in arts:
            meta = json.loads(a.classification_meta or "{}")
            assert meta.get("provider") == "golden"
            assert meta.get("prompt_version") == "v2"
            assert "importance_inputs" in meta
    finally:
        session.close()
