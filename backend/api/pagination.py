"""صفحه‌بندی مشترک فهرست‌ها (مرحله ۲).

قرارداد پاسخ: ``{items, total, page, page_size, has_more}`` — همان چیزی که
`screening/queue` از قبل داشت به‌علاوه‌ی `total`.

استفاده در یک endpoint تازه::

    page: int | None = Query(default=None, ge=1)
    page_size: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE)
    sort: str | None = Query(default=None, max_length=64)
    params = page_params(page=page, page_size=page_size, sort=sort,
                         sortable=SORT_FIELDS, default_sort="-created_at")

`sort` فقط از allowlist پذیرفته می‌شود (جهت با `-`)، و `page_size` حداکثر
`max_size` است؛ تخلف‌ها ۴۲۲ با `error.code=VALIDATION_ERROR` و
`error.details.fields` می‌دهند.

سازگاری: پارامتر قدیمی `limit` (و `offset` اگر endpoint داشت) هنوز کار می‌کند.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.api.errors import ApiError

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


@dataclass(frozen=True)
class PageParams:
    page: int
    page_size: int
    offset: int
    sort: str | None = None


def _bad(field: str, message: str, allowed: list[str] | None = None) -> ApiError:
    details: dict[str, Any] = {"fields": {field: message}}
    if allowed is not None:
        details["allowed"] = allowed
    return ApiError(422, "VALIDATION_ERROR", f"invalid {field}", details=details)


def page_params(
    *,
    page: int | None = None,
    page_size: int | None = None,
    limit: int | None = None,
    offset: int | None = None,
    sort: str | None = None,
    default_size: int = DEFAULT_PAGE_SIZE,
    max_size: int = MAX_PAGE_SIZE,
    sortable: tuple[str, ...] | None = None,
) -> PageParams:
    """اعتبارسنجی و ساخت پارامترهای صفحه؛ `limit`/`offset` قدیمی هم پذیرفته می‌شود."""
    if page is not None and page < 1:
        raise _bad("page", "must be >= 1")
    if offset is not None and offset < 0:
        raise _bad("offset", "must be >= 0")

    size = page_size if page_size is not None else (
        limit if limit is not None else default_size
    )
    if size < 1 or size > max_size:
        raise _bad("page_size", f"must be between 1 and {max_size}")

    if sort is not None:
        if sortable is None:
            raise _bad("sort", "not supported by this endpoint")
        field = sort[1:] if sort.startswith("-") else sort
        if field not in sortable:
            raise _bad("sort", "unknown field", allowed=sorted(sortable))

    if page is None or page < 1:
        page = (offset // size) + 1 if offset else 1
    start = offset if offset is not None else (page - 1) * size
    return PageParams(page=page, page_size=size, offset=start, sort=sort)


def page_response(items: list[Any], total: int, params: PageParams) -> dict[str, Any]:
    return {
        "items": items,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "has_more": params.page * params.page_size < total,
    }


def count_rows(db: Session, stmt: Any) -> int:
    return int(
        db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
        .scalar_one()
    )


def paginate(db: Session, stmt: Any, params: PageParams) -> tuple[list[Any], int]:
    """یک صفحه از `stmt` (تک‌موجودیتی) + total؛ ترتیب/فیلترها دست‌نخورده می‌مانند."""
    total = count_rows(db, stmt)
    rows = db.execute(stmt.limit(params.page_size).offset(params.offset)).scalars().all()
    return list(rows), total


def sort_expression(params: PageParams, columns: dict[str, Any], default: Any) -> Any:
    """ستون مرتب‌سازی مجاز (`-field` = نزولی) یا پیش‌فرض."""
    if not params.sort:
        return default
    descending = params.sort.startswith("-")
    column = columns[params.sort.lstrip("-")]
    return column.desc() if descending else column.asc()


def sort_rows(rows: list[Any], params: PageParams) -> list[Any]:
    """مرتب‌سازی در پایتون برای فهرست‌هایی که خودشان در حافظه فیلتر می‌شوند."""
    if not params.sort:
        return rows
    field = params.sort.lstrip("-")
    present = [r for r in rows if getattr(r, field, None) is not None]
    missing = [r for r in rows if getattr(r, field, None) is None]
    present.sort(key=lambda r: getattr(r, field), reverse=params.sort.startswith("-"))
    return present + missing
