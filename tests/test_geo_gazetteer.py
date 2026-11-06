"""Gazetteer قطعی: نام‌های مبهم، فارسی/انگلیسی، دقت."""
from __future__ import annotations

from domains.geo.gazetteer import geocode_text


def test_city_english_resolves_city_precision() -> None:
    r = geocode_text("Israeli settlers set fire to Palestinian olive grove near Ramallah")
    assert r["location_status"] == "resolved_city"
    assert r["location_precision"] == "city"
    assert r["country"] == "PS"
    assert r["latitude"] is not None


def test_country_mention_resolves_country_precision() -> None:
    r = geocode_text("South Africa's ANC on track for new lows in local polls")
    assert r["location_status"] == "resolved_country"
    assert r["location_precision"] == "country"
    assert r["country"] == "ZA"


def test_farsi_city_resolves() -> None:
    r = geocode_text("رویداد در تهران و اصفهان گزارش شد")
    # دو شهر ایران -> سطح کشور
    assert r["location_status"].startswith("resolved")
    assert r["country"] == "IR"


def test_ambiguous_georgia_without_context_unresolved() -> None:
    r = geocode_text("Georgia reports flooding")
    assert r["location_status"] == "unresolved"


def test_ambiguous_georgia_with_context_resolves() -> None:
    r = geocode_text("Georgia Tbilisi reports flooding")
    assert r["location_status"].startswith("resolved")
    assert r["country"] == "GE"


def test_conflicting_countries_unresolved() -> None:
    r = geocode_text("Talks between Iran and Israel in Geneva")
    # city? Geneva not in gazetteer; countries IR + IL conflict -> unresolved
    assert r["location_status"] == "unresolved"


def test_empty_unresolved() -> None:
    assert geocode_text(None)["location_status"] == "unresolved"
    assert geocode_text("")["location_status"] == "unresolved"


def test_new_city_resolves() -> None:
    r = geocode_text("Meeting in Pretoria and Cape Town")
    assert r["location_status"].startswith("resolved")


def test_unknown_never_on_map_feature() -> None:
    # geocode for unknown returns no coordinates
    r = geocode_text("A sunny day in the park")
    assert r["latitude"] is None and r["longitude"] is None
