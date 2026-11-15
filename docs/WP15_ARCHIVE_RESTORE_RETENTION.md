# WP-15 — Archive، Telegram، Restore و Retention

**تاریخ اجرا:** ۱۴ نوامبر ۲۰۲۶ · **HEAD:** `2d0e1bc`

## 1. WP-00 فقط‌خواندنی

Branch `step6a-analysis-dashboard`، HEAD `2d0e1bc`؛ ۲۰ modified + ۲۱ untracked.

## 2. Archive (§21.1)

- Archive ZIP، manifest، checksum، eligibility، validation، catalog، security checks reuse شدند (KEEP-13).
- path traversal / zip bomb / compression ratio / entry-size safeguards حفظ شدند.
- archive version، archive ID، timestamp، item count، omitted reasons، checksums، schema/app version ثبت می‌شوند.
- Secret/credential هرگز در Archive نیست.

## 3. Eligibility و Protected Records (§21.2)

- Eligibility از کد خوانده شد: classification، active dispatch، document/raw text/hash، provenance، event reference، importance، screening metadata، uncertainty.
- P0/P1، high uncertainty، Event، Claim، Evidence، Forecast، Outcome، Audit، AI logs، Memory، WorldState، lineage طبق policy محافظت می‌شوند.

## 4. Telegram Archive (§21.3)

- Telegram archive از Alert notification جداست.
- destination private/channel فقط با تأیید مالک.
- Bot Token write-only و encrypted.
- upload receipt: message/file ID، timestamp، size، checksum، archive version.
- split parts دارای manifest/checksum مستقل.
- retry قابل‌تطبیق با receipt؛ duplicate upload کنترل می‌شود.

## 5. Download/Verify/Restore (§21.4)

- archive از catalog انتخاب → remote metadata تطبیق → re-download → checksum parts+package → ZIP/Manifest validate → restore فقط به DB sandbox (هرگز live DB overwrite) → row count/ID/hash/relationship/provenance با Snapshot مقایسه.
- corruption/mismatch → `RESTORE_FAILED`؛ Source data پاک نمی‌شود.

## 6. Retention و Disk Monitoring (§21.5)

- Retention فعلی و candidate ages از کد خوانده شد (90/180/30 روز فقط baseline تاریخی).
- disk warning/critical thresholds از config (70%/85% فقط گزارش‌شده).
- `ARCHIVE_AUTO_PURGE_ENABLED=false` و `PURGE_DRY_RUN=true` پیش‌فرض ایمن (§3.4).
- Auto-Purge روشن نشد (ممنوع).

## 7. بررسی‌های اجراشده

- `pytest test_archive_api.py test_archive_catalog.py test_archive_entity_hardening.py test_archive_local.py test_archive_restore.py test_archive_restore_rel.py test_archive_split.py test_archive_validation_fail.py test_retention.py` → **۲۹ passed** (۲.۱۳s).
- `ruff check backend domains tests scripts source_bot` → ۰ خطا.
- `git diff --check` → پاک.

## 8. وضعیت WP-15

| معیار پذیرش | نتیجه |
|---|---|
| Archive ZIP/manifest/checksum | PASS |
| Eligibility/protected records | PASS |
| Telegram archive (receipt) | PASS (tests) |
| Download/verify/restore (sandbox) | PASS |
| Retention/disk monitoring | PASS |
| Auto-Purge پیش‌فرض خاموش | PASS |

**WP-15 در این نوبت کامل شد. WP-16 شروع نشد.**  
Limitation: Telegram live upload نیازمند Bot Token و destination تأییدشدهٔ مالک (credential). Auto-Purge خاموش ماند (مطابق policy).