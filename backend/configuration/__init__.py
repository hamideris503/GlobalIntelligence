"""Configuration control plane (F03.0).

قرارداد descriptor، چرخهٔ revision و پیش‌نمایش بدون ingest.
"""
from backend.configuration import descriptors, preview, service
from backend.configuration.errors import (
    ConfigurationError,
    Conflict,
    Invalid,
    NotFound,
    UnknownKind,
)

__all__ = [
    "ConfigurationError",
    "Conflict",
    "Invalid",
    "NotFound",
    "UnknownKind",
    "descriptors",
    "preview",
    "service",
]
