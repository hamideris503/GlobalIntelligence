"""Tests for the deterministic country-centroid resolver (advisory only).

The resolver never invents a point: unknown names stay unresolved, and a
resolved row is explicitly country-level (precision/confidence/source).
"""
from __future__ import annotations

import pytest

from domains.geo.resolver import resolve_location


@pytest.mark.parametrize("value", [None, "", "   "])
def test_empty_location_is_unresolved(value: str | None) -> None:
    result = resolve_location(value)
    assert result["status"] == "unresolved"
    assert result["latitude"] is None and result["longitude"] is None


def test_country_name_resolves_to_centroid_with_country_precision() -> None:
    result = resolve_location("Iran")
    assert result["country"] == "IR"
    assert result["status"] == "resolved_country"
    assert result["precision"] == "country"
    assert result["source"] == "country_centroid"
    assert result["confidence"] == 0.3


def test_substring_match_is_used_for_city_country_strings() -> None:
    result = resolve_location("Tehran, Iran")
    assert result["country"] == "IR"


def test_unknown_location_is_not_fabricated() -> None:
    result = resolve_location("Atlantis")
    assert result["status"] == "unresolved"
    assert all(result[key] is None for key in
               ("latitude", "longitude", "country", "precision", "source", "confidence"))
