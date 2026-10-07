# ============================================================
# ai.prompts — قالب‌های نسخه‌دار prompt
# ============================================================
"""
هر prompt باید نسخه داشته باشد و در Forecast/Analysis برای Reproducibility ثبت شود.

ساختار پیشنهادی: هر task یک دیکشنری {version, template}.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    version: str
    template: str

    def render(self, **kwargs: str) -> str:
        return self.template.format(**kwargs)


CLASSIFY_ARTICLE = PromptTemplate(
    name="classify_article",
    version="v1",
    template=(
        "You are an intelligence analyst. Classify the article below.\n"
        "Topics: {topics}\n\nArticle:\n{text}\n\nReturn a concise JSON."
    ),
)

EXTRACT_EVENT = PromptTemplate(
    name="extract_event",
    version="v1",
    template=(
        "Extract the event (type, actors, action, time, location) from the text below.\n\n"
        "Text:\n{text}"
    ),
)

__all__ = ["PromptTemplate", "CLASSIFY_ARTICLE", "EXTRACT_EVENT"]
