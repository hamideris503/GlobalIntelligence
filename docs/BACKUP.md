# BACKUP.md

> بکاپ زمان‌بندی‌شده و تست بازیابی (Step 6).
> ابزار: `scripts/db_backup.py` (dump/restore/verify + manifest + rotation؛ تست‌شده در Phase 45).

---

## 1. بکاپ دستی

```bash
python -m scripts.db_backup backup --dir backups --keep 7
```

خروجی: فایل dump + manifest؛ نگهداری چرخشی ۷ نسخه.

## 2. زمان‌بندی (cron روی سرور)

```cron
# هر روز ساعت 03:00 — بکاپ دیتابیس production
0 3 * * * cd /opt/globalintelligence && /usr/bin/python3 -m scripts.db_backup backup --dir /var/backups/gi --keep 14 >> /var/log/gi-backup.log 2>&1
```

نکته‌ها:

- cron روی هاست سرور اجرا می‌شود (نه داخل کانتینر)؛ به `PG_CONTAINER` (پیش‌فرض کانتینر postgres) دسترسی Docker لازم است.
- `.env` هرگز داخل بکاپ نیست (فقط داده‌ی DB).
- لاگ را گاهی چک کنید؛ خطای cron بی‌صدا می‌ماند.

## 3. تست بازیابی (دوره‌ای، حداقل ماهانه)

```bash
# روی یک DB جدا (هرگز روی production):
python -m scripts.db_backup restore --file <f> --target-db gi_restore_test
python -m scripts.db_backup verify --target-db gi_restore_test
```

`verify` شمارش جدول‌های کلیدی را با manifest مقایسه می‌کند. نتیجه را در PROGRESS.md ثبت کنید.
نام DB مقصد با `valid_target_db` اعتبارسنجی می‌شود (ضد injection).

## 4. بازیابی اضطراری

```bash
# ۱) سرویس‌ها را پایین بیاورید (compose down)، volume را نگه دارید
# ۲) restore روی DB اصلی طبق ران‌بوک حادثه (با تأیید مالک on-call)
# ۳) smoke: python -m scripts.smoke_check --base http://localhost:8000 --api-key <KEY>
```

> ⚠️ بازیابی روی production مخرب است؛ حتماً پیش از آن بکاپ تازه بگیرید.
