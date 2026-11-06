# صفحه‌بندی و فیلتر سمت سرور (الگوی مشترک)

منبع حقیقت: `backend/api/pagination.py`.

## قرارداد پاسخ

```json
{"items": [...], "total": 137, "page": 2, "page_size": 50, "has_more": true}
```

- `page` از ۱ شروع می‌شود؛ `page_size` پیش‌فرض ۵۰ و حداکثر ۲۰۰ (هر endpoint
  می‌تواند سقف کمتر بدهد، مثل `/api/screening/queue` که ۱۰۰ است).
- `total` تعداد کل ردیف‌های فیلترشده است، نه تعداد همین صفحه.
- `has_more` از `page * page_size < total` می‌آید.
- `sort` فقط از allowlist همان endpoint پذیرفته می‌شود؛ `-field` نزولی.
  مقدار نامعتبر → ۴۲۲ با `error.code=VALIDATION_ERROR` و
  `error.details.fields.sort` و `error.details.allowed`.

## افزودن به یک endpoint

```python
from backend.api.pagination import (
    MAX_PAGE_SIZE, page_params, page_response, paginate, sort_expression,
)

SORT_COLUMNS = {"created_at": Model.created_at, "name": Model.name}
SORT_FIELDS = tuple(SORT_COLUMNS)

@router.get("", response_model=None)
def list_x(
    limit: int = Query(default=50, ge=1, le=500),          # سازگاری قدیمی
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    sort: str | None = Query(default=None, max_length=64),
    db: Session = Depends(get_db),
):
    params = page_params(page=page, page_size=page_size, sort=sort,
                         sortable=SORT_FIELDS)
    stmt = select(Model).order_by(
        sort_expression(params, SORT_COLUMNS, Model.created_at.desc()))
    rows, total = paginate(db, stmt, params)
    return page_response(rows, total, params)
```

نکته‌ها:

- اگر endpoint قبلاً `limit`/`offset` دارد، آن‌ها را نگه دار و فقط وقتی
  `page`/`page_size`/`sort` آمده پاکت برگردان (نمونه: `/api/sources`).
  برای فهرست‌هایی که سمت پایتون فیلتر/مرتب می‌شوند از `sort_rows` استفاده کن.
- فیلترها همیشه allowlist باشند و هر فیلتر تازه تست داشته باشد.
- `paginate` برای `select(Model)` تک‌موجودیتی است؛ برای join چندموجودیتی
  `count_rows` + `db.execute(stmt.limit(...).offset(...))` را خودت بنویس.

## وضعیت مهاجرت

| endpoint | وضعیت |
| --- | --- |
| `/api/screening/queue` | مهاجرت‌شده (پاکت + `total`) |
| `/api/sources` | پاکت اختیاری؛ بدون `page`/`page_size`/`sort` همان لیست قدیمی |
| `/api/events` | پاکت اختیاری؛ بدون پارامترهای صفحه همان لیست قدیمی |
| بقیه (claims، decisions، forecasts، briefings، jobs، documents، alerts، inbox، geo) | الگوی بالا؛ هنوز مهاجرت نشده‌اند |
