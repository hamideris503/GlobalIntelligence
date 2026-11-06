"""`GET /api/geo/events` — GeoJSON رویدادهای دارای مختصات واقعی (مرحله ۳).

قواعد:
- فقط رکوردهایی برمی‌گردند که `latitude`/`longitude` ذخیره‌شده دارند؛ هیچ
  مختصاتی از نام کشور/شهر حدس زده نمی‌شود.
- `category` از نگاشت قطعی `domains/geo/category_map.py` می‌آید و نوع ناشناخته
  حذف می‌شود.
- شمار رویدادهای بدون مختصات در `metadata.without_location` می‌آید تا UI
  صادقانه آن را نشان دهد.
"""
from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any

from domains.geo.category_map import CATEGORIES, category_for
from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.api.errors import ApiError
from backend.api.schemas.geo import GeoCollection
from backend.database.models.event import Event
from backend.database.session import get_db

router = APIRouter(prefix="/api/geo", tags=["geo"])

DEFAULT_LIMIT = 2000
MAX_LIMIT = 5000


def _invalid(field: str, message: str) -> ApiError:
    return ApiError(
        422,
        "VALIDATION_ERROR",
        f"invalid {field}",
        details={"fields": {field: message}},
    )


def _parse_bbox(value: str | None) -> tuple[float, float, float, float] | None:
    """`min_lon,min_lat,max_lon,max_lat` → تاپل؛ نامعتبر → 422."""
    if value is None:
        return None
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 4:
        raise _invalid("bbox", "must be min_lon,min_lat,max_lon,max_lat")
    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
    except ValueError:
        raise _invalid("bbox", "coordinates must be numbers") from None
    if not all(math.isfinite(v) for v in (min_lon, min_lat, max_lon, max_lat)):
        raise _invalid("bbox", "coordinates must be finite")
    if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
        raise _invalid("bbox", "longitude must be between -180 and 180")
    if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise _invalid("bbox", "latitude must be between -90 and 90")
    if min_lon >= max_lon or min_lat >= max_lat:
        raise _invalid("bbox", "min values must be less than max values")
    return min_lon, min_lat, max_lon, max_lat


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return []
    return [str(x) for x in parsed] if isinstance(parsed, list) else []


@router.get("/events", response_model=GeoCollection)
def geo_events(
    request: Request,
    response: Response,
    bbox: str | None = Query(default=None, max_length=128),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    country: str | None = Query(default=None, max_length=8),
    category: str | None = Query(default=None, max_length=32),
    precision: str | None = Query(default=None, max_length=16),
    min_confidence: float | None = Query(default=None, ge=0, le=1),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    db: Session = Depends(get_db),
) -> Any:
    box = _parse_bbox(bbox)
    since, until = _utc(since), _utc(until)
    if since is not None and until is not None and since > until:
        raise _invalid("until", "must be after since")
    if category is not None:
        category = category.strip().lower()
        if category not in CATEGORIES:
            raise _invalid("category", "unknown category")
    if precision is not None:
        precision = precision.strip().lower()
        if precision not in ("city", "country"):
            raise _invalid("precision", "must be city or country")
    if country is not None:
        country = country.strip().upper() or None

    filters = []
    if since is not None:
        filters.append(Event.occurred_at >= since)
    if until is not None:
        filters.append(Event.occurred_at <= until)
    if country:
        filters.append(Event.country == country)
    if min_confidence is not None:
        filters.append(Event.confidence >= min_confidence)

    # بدون مختصات: همان فیلترهای زمانی/کشور/اطمینان، بدون شرط bbox (رویداد
    # بدون نقطه هیچ‌وقت در bbox نیست ولی باید در شمارنده دیده شود).
    missing = or_(Event.latitude.is_(None), Event.longitude.is_(None))
    without_location = int(
        db.execute(select(func.count(Event.id)).where(missing, *filters)).scalar_one()
    )

    located = [Event.latitude.is_not(None), Event.longitude.is_not(None)]
    if precision is not None:
        located.append(Event.location_precision == precision)
    if box is not None:
        min_lon, min_lat, max_lon, max_lat = box
        located.extend([
            Event.longitude >= min_lon,
            Event.longitude <= max_lon,
            Event.latitude >= min_lat,
            Event.latitude <= max_lat,
        ])
    stmt = (
        select(Event)
        .where(*located, *filters)
        .order_by(Event.occurred_at.is_(None), Event.occurred_at.desc())
    )
    rows = db.execute(stmt).scalars().all()

    features = []
    for row in rows:
        mapped = category_for(row.event_type)
        if mapped is None or (category is not None and mapped != category):
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row.longitude, row.latitude]},
            "properties": {
                "id": str(row.id),
                "category": mapped,
                "type": row.event_type,
                "title": row.action or row.event_type,
                "timestamp": row.occurred_at.isoformat() if row.occurred_at else None,
                "source": _json_list(row.sources),
                "confidence": row.confidence,
                "country": row.country,
                "location": row.location,
                "location_precision": row.location_precision,
                "location_source": row.location_source,
                "location_confidence": row.location_confidence,
            },
        })

    total = len(features)
    returned = features[:limit]
    latest = max((r.updated_at for r in rows if r.updated_at), default=None)
    etag = f'W/"geo-{total}-{without_location}-{int(latest.timestamp()) if latest else 0}"'
    headers = {"ETag": etag, "Cache-Control": "private, max-age=30"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    response.headers.update(headers)

    return {
        "type": "FeatureCollection",
        "features": returned,
        "metadata": {
            "total": total,
            "returned": len(returned),
            "limit": limit,
            "truncated": total > limit,
            "without_location": without_location,
        },
    }
