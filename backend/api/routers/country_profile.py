"""Country Profile API (Stage 99).

- GET /api/country-profiles           → لیست پروفایل‌ها
- GET /api/country-profiles/{code}    → جزئیات یک پروفایل
"""

from __future__ import annotations

from domains.country_profile import get_profile, list_profiles
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/country-profiles", tags=["country-profiles"])


@router.get("")
def list_country_profiles() -> list[dict]:
    return [p.as_dict() for p in list_profiles()]


@router.get("/{code}")
def get_country_profile(code: str) -> dict:
    p = get_profile(code)
    if p is None:
        raise HTTPException(status_code=404, detail="profile not found")
    return p.as_dict()