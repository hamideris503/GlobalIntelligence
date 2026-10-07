#!/bin/sh
# ============================================================
# GlobalIntelligence — Backend entrypoint
# قبل از اجرای سرور، migrationهای دیتابیس را اعمال می‌کند.
# قابل کنترل با RUN_MIGRATIONS=true|false (پیش‌فرض: true)
# ============================================================
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "[entrypoint] applying database migrations (alembic upgrade head)..."
  alembic upgrade head || {
    echo "[entrypoint] WARNING: migration failed. Starting server anyway (degraded)."
  }
else
  echo "[entrypoint] RUN_MIGRATIONS=false -> skipping migrations"
fi

exec "$@"
