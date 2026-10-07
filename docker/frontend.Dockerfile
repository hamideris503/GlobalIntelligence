# ============================================================
# GlobalIntelligence — Frontend image (development: Vite dev server)
# ============================================================
FROM node:20-slim

WORKDIR /app

# در صورت نیاز به رجیستری جایگزین npm برای شبکه‌های محدود
ARG NPM_REGISTRY=https://registry.npmjs.org
RUN npm config set registry "${NPM_REGISTRY}"

COPY apps/web/package.json ./
RUN npm install

COPY apps/web ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
