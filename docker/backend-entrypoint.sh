#!/bin/sh
# ============================================================
# GlobalIntelligence — Backend entrypoint
# قبل از اجرای سرور، migrationهای دیتابیس را اعمال می‌کند.
#   RUN_MIGRATIONS=true|false   (پیش‌فرض true)
#   APP_ENV=production          → در صورت شکست migration، fail-fast
# ============================================================
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "[entrypoint] applying database migrations (alembic upgrade head)..."
  if ! alembic upgrade head; then
    if [ "${APP_ENV}" = "production" ] || [ "${APP_ENV}" = "staging" ]; then
      echo "[entrypoint] FATAL: migration failed in ${APP_ENV}. Aborting."
      exit 1
    fi
    echo "[entrypoint] WARNING: migration failed. Starting server anyway (development)."
  fi
else
  echo "[entrypoint] RUN_MIGRATIONS=false -> skipping migrations"
fi

exec "$@"
