# بررسی مرحلهٔ ۵ — صندوق اطلاعات و غربالگری (پیش از کدنویسی)

## وضعیت فعلی UI
هر دو صفحه **کاملاً دادهٔ نمونه** هستند:
- `inbox()`: چهار KPI ثابت (۲۳/۴۱/۱۷/۹)، نوار فیلتر بدون هندلر مؤثر، جدول generic نمونه، دکمهٔ «ذخیرهٔ نمای فیلتر» که تصمیم گرفته شده حذف شود.
- `screening()`: چهار KPI ثابت (۳۷/۷۴٪/۹٪/نامشخص)، سه `review-item` ساختگی، بخش «چهار حقیقت مستقل» و جدول dispatch نمونه. دکمه‌های approve/reject فقط toast نمایشی می‌دهند.

## endpointهای موجود
| endpoint | نقش فعلی | خروجی |
|---|---|---|
| `GET /api/classify/articles` (+`/{id}`) | فهرست مقالات طبقه‌بندی‌شده | id, document_id, title, topics, entities, priority, duplicate_cluster, analysis_status (implicit) |
| `GET /api/screening/queue` | صف بازبینی | صفحه‌بندی‌شده: article_id, title, source_name, priority, screening (خروجی ماشین), screening_status, review_required/reasons/acknowledged |
| `POST /api/screening/review/{id}/ack` | ack سازگار موجود | human_review در classification_meta (نه overwrite) |
| `POST /api/screening/screen` | اجرای screening | decision |
| `GET /api/dedup/clusters` | خوشه‌های dedup | article_id, document_id, source_id, cluster |
| `GET /api/ingest/documents` | اسناد خام | id, source_id, url, title, priority, retrieved_at |
| `GET /api/dispatch/status`, `/jobs` | وضعیت dispatch | شمار و صفحه‌بندی jobها |
| `GET /api/local-runtimes/status` | وضعیت Kev/Laya | enabled/loaded/state هر runtime |

## چه چیزی کم است
1. `GET /api/inbox` و `GET /api/inbox/summary` وجود ندارند (KPI صندوق قابل محاسبه نیست).
2. `POST /api/screening/review/{id}/decision` وجود ندارد (فقط `ack`).
3. `GET /api/screening/summary` وجود ندارد.
4. جدول `human_reviews` وجود ندارد؛ تصمیم انسانی فعلاً فقط داخل `classification_meta` ذخیره می‌شود.
5. UI هر دو صفحه داده واقعی ندارد.

## تصمیم
- جدول `human_reviews` با migration (append-only، جدا از خروجی ماشین).
- `ack` موجود حفظ می‌شود؛ `decision` جدید کنار آن.
- KPIها با تعریف صریح؛ هر عددی که قابل محاسبه نباشد `null` می‌شود.
