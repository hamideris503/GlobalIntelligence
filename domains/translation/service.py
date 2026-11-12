"""Offline translation service (Stage 101).

- فقط برای نمایش: تحلیل روی متن اصلی.
- cache بر پایهٔ hash(text) + src + dst + model_version.
- invalidation با تغییر مدل/متن.
- خطای ترجمه نباید دریافت خبر/تحلیل را متوقف کند (None + available=False).
- backend قابل تزریق (mock/testable); بدون وابستگی به مدل واقعی.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol


class TranslatorBackend(Protocol):
    def translate(self, text: str, src: str, dst: str) -> str: ...


@dataclass
class TranslationResult:
    source_text: str
    translated_text: str | None
    src: str
    dst: str
    model: str
    model_version: str
    cache_key: str
    available: bool
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "src": self.src,
            "dst": self.dst,
            "model": self.model,
            "model_version": self.model_version,
            "available": self.available,
            "translated_text": self.translated_text,
            "error": self.error,
        }


def _cache_key(text: str, src: str, dst: str, model_version: str) -> str:
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{h}:{src}:{dst}:{model_version}"


class TranslationService:
    def __init__(
        self,
        backend: TranslatorBackend | None = None,
        *,
        model: str = "none",
        model_version: str = "0",
        cache: dict[str, str] | None = None,
    ) -> None:
        self.backend = backend
        self.model = model
        self.model_version = model_version
        self.cache = cache if cache is not None else {}

    def _available(self) -> bool:
        return self.backend is not None

    def translate(self, text: str, *, src: str = "en", dst: str = "fa") -> TranslationResult:
        key = _cache_key(text, src, dst, self.model_version)
        # cache hit
        if key in self.cache:
            return TranslationResult(
                source_text=text,
                translated_text=self.cache[key],
                src=src,
                dst=dst,
                model=self.model,
                model_version=self.model_version,
                cache_key=key,
                available=True,
            )
        if not self._available():
            return TranslationResult(
                source_text=text,
                translated_text=None,
                src=src,
                dst=dst,
                model=self.model,
                model_version=self.model_version,
                cache_key=key,
                available=False,
                error="no backend configured",
            )
        try:
            out = self.backend.translate(text, src, dst)  # type: ignore[union-attr]
        except Exception as exc:  # noqa: BLE001
            return TranslationResult(
                source_text=text,
                translated_text=None,
                src=src,
                dst=dst,
                model=self.model,
                model_version=self.model_version,
                cache_key=key,
                available=False,
                error=f"{type(exc).__name__}: {exc}",
            )
        # store cache
        self.cache[key] = out
        return TranslationResult(
            source_text=text,
            translated_text=out,
            src=src,
            dst=dst,
            model=self.model,
            model_version=self.model_version,
            cache_key=key,
            available=True,
        )

    def translate_batch(self, texts: list[str], *, src: str = "en", dst: str = "fa") -> list[TranslationResult]:
        return [self.translate(t, src=src, dst=dst) for t in texts]

    def invalidate(self, text: str, *, src: str = "en", dst: str = "fa") -> None:
        key = _cache_key(text, src, dst, self.model_version)
        self.cache.pop(key, None)