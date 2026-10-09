# VPS_DEPLOYMENT.md

> استقرار production روی VPS (Phase 48).
> وضعیت: automation و مستندات آماده؛ **استقرار زنده BLOCKED** (بدون دسترسی به سرور).

---

## 1. پیش‌نیاز سرور

- Ubuntu 22.04+ (یا Debian 12+) با حداقل 2 CPU و 4GB RAM
- Docker Engine + Compose plugin نصب‌شده
- کاربر با دسترسی sudo + کلید SSH
- پورت‌های 80/443 (بعداً reverse proxy) — فعلاً همه‌چیز روی 127.0.0.1 است

## 2. آماده‌سازی secretها (روی سرور، دستی)

`.env` **هرگز** منتقل نمی‌شود (اسکریپت refuse می‌کند). روی سرور بسازید:

```bash
mkdir -p /opt/globalintelligence && cd /opt/globalintelligence
cp .env.example .env   # بعد از انتقال فایل‌ها (مرحله ۳)
nano .env              # API_KEY, SECRET_KEY, POSTGRES_PASSWORD قوی + MOCK_MODE=false
```

تولید مقدار قوی:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 3. استقرار خودکار (dry-run اول)

```bash
# فقط نمایش فرمان‌ها (امن، بدون اتصال واقعی لازم نیست... به host نیاز دارد ولی وصل نمی‌شود)
python -m scripts.deploy_vps --host <IP> --user root

# اجرای واقعی (نیازمند SSH با کلید، بدون passphraseِ تعاملی)
python -m scripts.deploy_vps --host <IP> --user root --key ~/.ssh/id_rsa --live
```

مراحل: بررسی docker ← ساخت پوشه ← scp فایل‌ها (بدون `.env`) ←
`compose up -d --build` با prod override ← smoke روی `/health/db`.

## 4. پس از استقرار

```bash
# روی سرور:
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs backend --tail 20
python -m scripts.smoke_check --base http://localhost:8000 --api-key <KEY>
```

## 5. کارهای مانده برای production واقعی

- [ ] Reverse proxy (Caddy/Nginx) + TLS (Let's Encrypt) — Phase 50
- [ ] زمان‌بندی بکاپ (`scripts/db_backup.py` در cron) — Phase 49/50
- [ ] Monitoring/alerting خارجی — Phase 50
- [ ] استقرار زنده (BLOCKED: دسترسی به VPS لازم است)

## 6. بازگشت (rollback)

```bash
cd /opt/globalintelligence
docker compose -f docker-compose.yml -f docker-compose.prod.yml down
# داده در volume pg_data می‌ماند؛ بکاپ پیش از تغییر بگیرید (Phase 45)
```
