# n8n Integration (Phase 4)

n8n به‌عنوان موتور orchestration/زمان‌بندی استفاده می‌شود. **منطق علمی و تحلیلی
در Backend/Python می‌ماند** (بند 8)؛ n8n فقط trigger و هماهنگی می‌کند.

## اجرا
n8n در `docker-compose.yml` بالا می‌آید و از طریق شبکه‌ی `gi_net` به backend
با آدرس `http://backend:8000` دسترسی دارد.

| مورد | مقدار |
|---|---|
| URL | http://localhost:5678 |
| User/Pass | از `.env` (`N8N_BASIC_AUTH_*`) — پیش‌فرض admin / change-me-in-production |
| Backend base URL (داخل شبکه) | http://backend:8000 |

## Workflow نمونه: Trigger → Backend → Database

فایل: `workflows/phase4-trigger-backend-database.json`

مسیر:
```
Schedule Trigger (هر ۵ دقیقه)
   ↓  POST /api/jobs/trigger
Backend (FastAPI)  →  INSERT INTO job_runs (PostgreSQL)
```

## نحوه‌ی import

### گزینه ۱ — از رابط وب (ساده‌ترین)
1. http://localhost:5678 را باز کنید.
2. Workflows → **Import from File** → فایل JSON را انتخاب کنید.
3. Workflow را **Active** کنید.

### گزینه ۲ — با CLI داخل کانتینر
```powershell
docker compose exec -T n8n n8n import:workflow --input=/data/phase4.json
```
(ابتدا فایل را به کانتینر کپی کنید یا از volume استفاده کنید.)

## تست دستی مسیر (بدون n8n)
```powershell
# trigger یک job
curl -X POST http://localhost:8000/api/jobs/trigger -H "Content-Type: application/json" -d "{\"job_name\":\"manual_test\",\"source\":\"manual\"}"

# مشاهده آخرین اجراها
curl http://localhost:8000/api/jobs
```
انتظار: `job_runs` در PostgreSQL یک رکورد جدید داشته باشد.
