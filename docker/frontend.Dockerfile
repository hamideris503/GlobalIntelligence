# ============================================================
# GlobalIntelligence — Frontend image (development: Vite dev server)
# ============================================================
FROM node:20-slim

WORKDIR /app

COPY apps/web/package.json ./
RUN npm install

COPY apps/web ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
