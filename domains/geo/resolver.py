"""Minimal deterministic geospatial resolver.

shortcut: static country-centroid map only (no real geocoder), upgrade to a
proper geocoding provider (Nominatim/GeoNames) when credentials/infra allow.
Confidence for a centroid is 0.3 (country-level precision, not point).
"""
from __future__ import annotations

# Country name (lowercased) / ISO-ish code -> (lat, lon, iso2)
_COUNTRY_CENTROIDS: dict[str, tuple[float, float, str]] = {
    "iran": (32.4279, 53.6880, "IR"),
    "iran, islamic republic of": (32.4279, 53.6880, "IR"),
    "israel": (31.0461, 34.8516, "IL"),
    "palestine": (31.9522, 35.2332, "PS"),
    "gaza": (31.5, 34.47, "PS"),
    "lebanon": (33.8547, 35.8623, "LB"),
    "syria": (34.8021, 38.9968, "SY"),
    "iraq": (33.2232, 43.6793, "IQ"),
    "saudi arabia": (23.8859, 45.0792, "SA"),
    "yemen": (15.5527, 48.5164, "YE"),
    "turkey": (38.9637, 35.2433, "TR"),
    "russia": (61.5240, 105.3188, "RU"),
    "ukraine": (48.3794, 31.1656, "UA"),
    "china": (35.8617, 104.1954, "CN"),
    "united states": (37.0902, -95.7129, "US"),
    "usa": (37.0902, -95.7129, "US"),
    "united kingdom": (55.3781, -3.4360, "GB"),
    "uk": (55.3781, -3.4360, "GB"),
    "france": (46.2276, 2.2137, "FR"),
    "germany": (51.1657, 10.4515, "DE"),
    "india": (20.5937, 78.9629, "IN"),
    "pakistan": (30.3753, 69.3451, "PK"),
    "afghanistan": (33.9391, 67.7100, "AF"),
}


def resolve_location(location: str | None) -> dict:
    """Return a dict with lat, lon, country, precision, source, status, confidence."""
    if not location or not location.strip():
        return {"latitude": None, "longitude": None, "country": None,
                "precision": None, "source": None, "status": "unresolved",
                "confidence": None}
    key = location.strip().lower()
    # try direct match
    if key in _COUNTRY_CENTROIDS:
        lat, lon, iso = _COUNTRY_CENTROIDS[key]
        return {"latitude": lat, "longitude": lon, "country": iso,
                "precision": "country", "source": "country_centroid",
                "status": "resolved_country", "confidence": 0.3}
    # try substring match
    for name, (lat, lon, iso) in _COUNTRY_CENTROIDS.items():
        if name in key or key in name:
            return {"latitude": lat, "longitude": lon, "country": iso,
                    "precision": "country", "source": "country_centroid",
                    "status": "resolved_country", "confidence": 0.3}
    return {"latitude": None, "longitude": None, "country": None,
            "precision": None, "source": None, "status": "unresolved",
            "confidence": None}
