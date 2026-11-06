# بررسی صفحهٔ «منابع» (مرحلهٔ ۴) — گزارش پیش از کدنویسی

## وضعیت فعلی UI
- `sources()` در `backend/static/index.html` کاملاً **دادهٔ نمونه** است: اعداد ثابت (۱۲۸ منبع، ۹۴ فعال، ۸ نیازمند بررسی)، ۴ ردیف ساختگی با دامنه‌های `*.demo`، و یک قیف دریافت نمایشی.
- تنها اتصال واقعی: `loadSourcesReal()` که `GET /api/sources/stats` را می‌خواند و فقط «منابع ثبت‌شده» را با `#srcCount` پر می‌کند. بقیهٔ اعداد نمونه باقی مانده‌اند.
- هیچ فهرست واقعی، جست‌وجو، فیلتر، مرتب‌سازی، صفحه‌بندی، حالت خالی/خطا، یا فرم ساخت/ویرایش ندارد.
- دکمه‌های `data-action="source"` و `fetchAll` بدون هندلر مؤثر هستند (fail silently).

## وضعیت backend (موجود)
| endpoint | نقش | وضعیت |
|---|---|---|
| `GET /api/sources` | viewer | ✅ فهرست + فیلتر (`active`, `country`, `type`, `category`, `validation_status`) + صفحه‌بندی (`page/page_size/sort`) |
| `GET /api/sources/{id}` | viewer | ✅ |
| `GET /api/sources/{id}/stats` | viewer | ✅ (مرحلهٔ ۴ — تعداد سند/مقاله، last_success/error، آخرین job) |
| `GET /api/sources/stats` | viewer | ✅ (مرحلهٔ ۴ — تجمیعی) |
| `POST /api/sources` | admin | ✅ ساخت |
| `PATCH /api/sources/{id}` | admin | ✅ ویرایش (شامل `active`) |
| `POST /api/sources/{id}/preview` | admin | ✅ preview بدون ingest |
| `POST /api/sources/{id}/health` | admin | ✅ ثبت سلامت |
| `POST /api/sources/{id}/recheck` | admin | ✅ اعتبارسنجی |
| `GET /api/sources/export/all` | viewer | ✅ خروجی |

## چه چیزی کم است
1. **UI کامل صفحهٔ منابع** (اصلی‌ترین کمبود): فهرست واقعی، جست‌وجو، فیلتر وضعیت/نوع، مرتب‌سازی، صفحه‌بندی، حالت‌های بارگذاری/خالی/خطا، و فرم ساخت/ویرایش + فعال/غیرفعال + preview فقط برای admin.
2. آمار هر منبع با فهرست ادغام نشده (نرخ خطا/سلامت جداگانه صدا زده نمی‌شود).
3. قیف دریافت واقعی (`GET /api/ingest/stats`) وجود ندارد — بک‌اند آن را ندارد؛ فعلاً نمایشی می‌ماند یا از stats تجمیعی ساخته می‌شود.

## تصمیم
- **بدون migration جدید**: همهٔ دادهٔ لازم از endpointهای موجود می‌آید.
- UI با fetch از `/api/sources` (صفحه‌بندی‌شده) + `/api/sources/stats` ساخته می‌شود؛ فرم‌ها فقط برای admin (بر اساس `giCurrentUser.role`).
- دکمه‌های بی‌کار حذف یا به endpoint واقعی وصل می‌شوند.
