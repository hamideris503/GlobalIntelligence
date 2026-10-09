# ============================================================
# GlobalIntelligence — Frontend production image (multi-stage)
# مرحله‌ی build با Node و سرو فایل‌های استاتیک با nginx (SPA fallback).
# ============================================================

# --- stage 1: build ---
FROM node:20-slim AS builder

WORKDIR /app

ARG NPM_REGISTRY=https://registry.npmjs.org
RUN npm config set registry "${NPM_REGISTRY}"

COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

COPY apps/web ./
RUN npm run build

# --- stage 2: serve ---
FROM nginx:1.27-alpine AS runtime

COPY docker/nginx-spa.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://localhost/ || exit 1
