"""Promptهای نسخه‌دار برای طبقه‌بندی و استخراج (Phase 10)."""
from __future__ import annotations

from backend.ai.prompts import PromptTemplate

CLASSIFY_ARTICLE = PromptTemplate(
    name="classify_article",
    version="v1",
    template=(
        "You are an intelligence analyst. Analyze the article and return JSON only.\n\n"
        "Allowed topics: {topics}\n"
        "Allowed countries (ISO-3166 alpha-2 or empty): {countries}\n\n"
        "Article title: {title}\n"
        "Article text:\n{text}\n\n"
        "Return JSON with keys: topics (list), country (string or null), "
        "entities (list of objects with name/type), sentiment (number -1..1), "
        "stance (string), summary (string)."
    ),
)

EXTRACT_ENTITIES = PromptTemplate(
    name="extract_entities",
    version="v1",
    template=(
        "Extract named entities from the text. Allowed types: {entity_types}.\n\n"
        "Text:\n{text}\n\n"
        "Return JSON with key 'entities': list of {name, type}."
    ),
)

__all__ = ["CLASSIFY_ARTICLE", "EXTRACT_ENTITIES"]
