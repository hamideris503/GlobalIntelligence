# STAGING.md

> محیط staging جدا از dev برای تأیید انتشار (Phase 47).
> اصل: staging هرگز به داده/پورت dev دست نمی‌زند.

---

## 1. بالا آوردن

```bash
docker compose -p gi_staging -f docker-compose.yml \
  -f docker-compose.staging.yml up -d --build
```

- پورت‌ها (جدا از dev): backend `8001`، frontend `5174`، postgres `5433`، n8n `5679`.
- نام کانتینرها `gi_staging_*` و volumeها جدا (`-p` + override).
- `APP_ENV=staging`، `MOCK_MODE=true`، `DEBUG=false` (امن؛ بدون نیاز به کلید واقعی).
- migration در entrypoint خودکار است و در staging شکست → fail-fast.

## 2. Smoke test

```bash
python -m scripts.smoke_check --base http://localhost:8001 --api-key <KEY>
```

۹ چک: health، health/db، auth (بدون کلید 401)، شش endpoint محافظت‌شده.
کد خروج ۰ یعنی همه سبز.

## 3. جمع‌کردن (با حذف volume)

```bash
docker compose -p gi_staging -f docker-compose.yml \
  -f docker-compose.staging.yml down -v
```

## 4. نکات امنیتی

- خروجی `docker compose config` مقادیر `.env` (کلیدها/رمزها) را **درون‌یابی و چاپ** می‌کند؛
  هرگز آن را به اشتراک نگذارید یا در لاگ ذخیره نکنید.
- staging با داده‌ی تازه کار می‌کند؛ migration روی dev اجرا نمی‌شود.
- compose لیست `ports` را merge می‌کند؛ در این فایل با `!override` جایگزین شده
  تا پورت dev (8000/...) دوباره bind نشود.

## 5. عیب‌یابی

| علامت | علت محتمل |
|---|---|
| `port is already allocated` | override پورت جا افتاده؛ `config` را بدون چاپ secret بررسی کن |
| `container name conflict` | `container_name` تکراری؛ پیشوند `gi_staging_` لازم است |
| backend بالا نمی‌آید | لاگ entrypoint (migration) را ببین: `docker logs gi_staging_backend` |
