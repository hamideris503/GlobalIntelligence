# ============================================================
# GlobalIntelligence — Backend image (development)
# ============================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# در صورت نیاز به آینه (mirror) داخلی برای شبکه‌های محدود، می‌توان
# PIP_INDEX_URL و PIP_TRUSTED_HOST را از build-arg ست کرد.
ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}

WORKDIR /app

# نصب وابستگی‌ها جداگانه برای بهره‌گیری از cache
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install -r backend/requirements.txt

# کپی سورس backend + تنظیمات alembic + migrations
COPY backend ./backend
COPY alembic.ini ./alembic.ini
COPY db ./db

# entrypoint اعمال migration پیش از اجرای سرور
COPY docker/backend-entrypoint.sh /usr/local/bin/backend-entrypoint.sh
RUN chmod +x /usr/local/bin/backend-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

ENTRYPOINT ["backend-entrypoint.sh"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
