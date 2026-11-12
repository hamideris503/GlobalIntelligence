"""Tests for Offline Translation (Stage 101)."""

from __future__ import annotations

from domains.translation.service import TranslationService


class FakeBackend:
    def __init__(self):
        self.calls = 0

    def translate(self, text, src, dst):
        self.calls += 1
        return f"[{src}->{dst}] {text}"


def test_translate_with_backend():
    b = FakeBackend()
    svc = TranslationService(backend=b, model="fake", model_version="1")
    r = svc.translate("hello", src="en", dst="fa")
    assert r.available is True
    assert r.translated_text == "[en->fa] hello"
    assert r.error is None


def test_cache_hit_no_second_call():
    b = FakeBackend()
    svc = TranslationService(backend=b, model="fake", model_version="1")
    r1 = svc.translate("hello")
    r2 = svc.translate("hello")
    assert r1.cache_key == r2.cache_key
    assert r2.translated_text == r1.translated_text
    assert b.calls == 1


def test_no_backend_returns_unavailable():
    svc = TranslationService(model="none", model_version="0")
    r = svc.translate("hello")
    assert r.available is False
    assert r.translated_text is None
    assert "no backend" in (r.error or "")


def test_backend_error_returns_unavailable():
    class Boom:
        def translate(self, text, src, dst):
            raise RuntimeError("boom")

    svc = TranslationService(backend=Boom(), model="fake", model_version="1")
    r = svc.translate("hello")
    assert r.available is False
    assert r.translated_text is None
    assert "RuntimeError" in (r.error or "")


def test_invalidation():
    b = FakeBackend()
    svc = TranslationService(backend=b, model="fake", model_version="1")
    svc.translate("hello")
    assert b.calls == 1
    svc.invalidate("hello")
    svc.translate("hello")
    assert b.calls == 2


def test_model_version_change_invalidates_cache():
    b = FakeBackend()
    cache = {}
    svc1 = TranslationService(backend=b, model="fake", model_version="1", cache=cache)
    svc1.translate("hello")
    assert b.calls == 1
    # new service with different version shares cache but key differs
    svc2 = TranslationService(backend=b, model="fake", model_version="2", cache=cache)
    r = svc2.translate("hello")
    assert r.available is True
    assert b.calls == 2


def test_original_text_preserved():
    b = FakeBackend()
    svc = TranslationService(backend=b, model="fake", model_version="1")
    r = svc.translate("hello world")
    assert r.source_text == "hello world"


def test_batch():
    b = FakeBackend()
    svc = TranslationService(backend=b, model="fake", model_version="1")
    rs = svc.translate_batch(["a", "b"])
    assert len(rs) == 2
    assert all(r.available for r in rs)
