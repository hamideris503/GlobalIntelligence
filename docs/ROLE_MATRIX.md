# ماتریس نقش‌ها — endpoint → حداقل نقش

منبع حقیقت: `backend/auth/deps.py` (`required_role` + `access_guard`). این فایل
از روی جدول واقعی مسیرهای اپلیکیشن تولید شده است؛ اگر endpoint جدیدی اضافه شد
که در این نگاشت نیست، قاعده‌ی پیش‌فرض این است:

- متد تغییردهنده (POST/PUT/PATCH/DELETE) → `admin`
- اجرای تحلیل/استخراج (لیست `ANALYST_WRITE_PATHS`) → `analyst`
- خواندن → `viewer` (به‌جز تنظیمات/آرشیو/audit/ops که `admin` است)

`X-API-Key` نقش `admin` می‌گیرد، پس n8n و اسکریپت‌ها بدون تغییر کار می‌کنند.
ابزارهای مستقل: `/health`, `/health/db`, `/api/auth/*` (ورود عمومی‌اند؛
`/api/auth/me` و خروج خودشان `require_user` دارند).

## `/jobs`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/jobs/trigger` | admin |
| GET | `/api/jobs` | viewer |

## `/ai`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/ai/generate` | analyst |
| GET | `/api/ai/providers` | viewer |
| GET | `/api/ai/status` | viewer |
| POST | `/api/ai/chat` | analyst |

## `/ai-routing`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/ai-routing/record` | admin |
| GET | `/api/ai-routing/stats` | viewer |
| GET | `/api/ai-routing/routes` | viewer |
| POST | `/api/ai-routing/apply` | admin |

## `/alerts`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/alerts/rules` | admin |
| GET | `/api/alerts/rules` | viewer |
| PATCH | `/api/alerts/rules/{rule_id}` | admin |
| POST | `/api/alerts/evaluate` | analyst |
| GET | `/api/alerts` | viewer |
| GET | `/api/alerts/{alert_id}` | viewer |
| POST | `/api/alerts/{alert_id}/ack` | admin |
| POST | `/api/alerts/{alert_id}/resolve` | admin |
| POST | `/api/alerts/deliver/pending` | admin |
| POST | `/api/alerts/{alert_id}/deliver/{channel}` | admin |

## `/audit`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/audit/log` | analyst |
| GET | `/api/audit/records` | admin |
| POST | `/api/audit/replay` | analyst |
| GET | `/api/audit/engines` | admin |

## `/briefings`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/briefings/daily` | analyst |
| POST | `/api/briefings/weekly` | analyst |
| GET | `/api/briefings` | viewer |
| GET | `/api/briefings/{briefing_id}` | viewer |

## `/sources`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| GET | `/api/sources` | viewer |
| POST | `/api/sources` | admin |
| GET | `/api/sources/{source_id}` | viewer |
| PATCH | `/api/sources/{source_id}` | admin |
| POST | `/api/sources/{source_id}/preview` | admin |
| POST | `/api/sources/{source_id}/health` | admin |
| POST | `/api/sources/{source_id}/recheck` | admin |
| GET | `/api/sources/export/all` | viewer |
| GET | `/api/sources/{source_id}/stats` | viewer |
| GET | `/api/sources/stats` | viewer |

## `/configuration`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| GET | `/api/configuration/definitions` | viewer |
| GET | `/api/configuration/definitions/{kind}` | viewer |
| GET | `/api/configuration/instances` | viewer |
| POST | `/api/configuration/instances` | admin |
| GET | `/api/configuration/instances/{instance_id}` | viewer |
| POST | `/api/configuration/instances/{instance_id}/revisions` | admin |
| POST | `/api/configuration/instances/{instance_id}/revisions/{number}/validate` | admin |
| POST | `/api/configuration/instances/{instance_id}/revisions/{number}/test` | admin |
| POST | `/api/configuration/instances/{instance_id}/revisions/{number}/activate` | admin |
| POST | `/api/configuration/instances/{instance_id}/rollback` | admin |

## `/ingest`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/ingest` | admin |
| POST | `/api/ingest/all` | admin |
| POST | `/api/ingest/bot` | admin |
| POST | `/api/ingest/jobs` | admin |
| GET | `/api/ingest/jobs/{job_id}` | viewer |
| GET | `/api/ingest/documents` | viewer |

## `/dedup`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| GET | `/api/dedup/clusters` | viewer |
| POST | `/api/dedup/run` | analyst |

## `/classify`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/classify/run` | analyst |
| GET | `/api/classify/articles` | viewer |
| GET | `/api/classify/articles/{article_id}` | viewer |

## `/debate`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/debate/run` | analyst |
| GET | `/api/debate/runs` | viewer |
| GET | `/api/debate/runs/{run_id}` | viewer |
| GET | `/api/debate/scorecard` | viewer |

## `/events`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/events/extract` | analyst |
| GET | `/api/events` | viewer |

## `/geo`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| GET | `/api/geo/events` | viewer |

`/api/geo/events` دادهٔ تحلیلی خواندنی است (GeoJSON)؛ با کوکی نشست same-origin
کار می‌کند و `X-API-Key` هم مثل بقیهٔ مسیرها نقش `admin` می‌گیرد.

## `/claims`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/claims/extract` | analyst |
| POST | `/api/claims/evidence` | analyst |
| GET | `/api/claims` | viewer |
| GET | `/api/claims/{claim_id}/evidence` | viewer |

## `/independence`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/independence/run` | analyst |
| GET | `/api/independence/dependencies` | viewer |
| POST | `/api/independence/dependencies` | admin |
| DELETE | `/api/independence/dependencies/{dependency_id}` | admin |
| GET | `/api/independence/groups` | viewer |

## `/graph`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/graph/extract` | analyst |
| GET | `/api/graph/entities` | viewer |
| GET | `/api/graph/entities/{entity_id}` | viewer |
| GET | `/api/graph/relationships` | viewer |
| GET | `/api/graph/neighbors/{entity_id}` | viewer |

## `/economic`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/economic/fetch` | analyst |
| GET | `/api/economic/observations` | viewer |
| GET | `/api/economic/indicators` | viewer |
| GET | `/api/economic/latest` | viewer |

## `/markets`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/markets/fetch` | analyst |
| GET | `/api/markets/observations` | viewer |
| GET | `/api/markets/symbols` | viewer |
| GET | `/api/markets/latest` | viewer |

## `/world-state`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/world-state/build` | analyst |
| GET | `/api/world-state/current` | viewer |
| GET | `/api/world-state/history` | viewer |

## `/memory`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/memory/archive` | admin |
| GET | `/api/memory/timeline` | viewer |
| GET | `/api/memory/stats` | viewer |
| GET | `/api/memory/records` | viewer |

## `/analogues`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| GET | `/api/analogues` | viewer |
| GET | `/api/analogues/{analogue_id}/aftermath` | viewer |

## `/archive`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| GET | `/api/archive/storage` | admin |
| GET | `/api/archive/settings` | admin |
| GET | `/api/archive/catalog` | admin |
| GET | `/api/archive/catalog/{archive_id}` | admin |
| POST | `/api/archive/validate` | admin |
| POST | `/api/archive/restore/dry-run` | admin |
| POST | `/api/archive/restore` | admin |
| GET | `/api/archive/purge/preview` | admin |
| POST | `/api/archive/telegram/{archive_id}` | admin |

## `/macro`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/macro/analyze` | analyst |
| GET | `/api/macro/assessments` | viewer |
| GET | `/api/macro/overview` | viewer |

## `/geopolitics`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/geopolitics/analyze` | analyst |
| GET | `/api/geopolitics/assessments` | viewer |
| GET | `/api/geopolitics/tensions` | viewer |

## `/society`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/society/analyze` | analyst |
| GET | `/api/society/assessments` | viewer |
| GET | `/api/society/mood` | viewer |

## `/narratives`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/narratives/build` | analyst |
| GET | `/api/narratives` | viewer |
| GET | `/api/narratives/{narrative_id}` | viewer |

## `/outcomes`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/outcomes/resolve` | analyst |
| GET | `/api/outcomes` | viewer |
| GET | `/api/outcomes/pending` | viewer |

## `/ops`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| GET | `/api/ops/status` | admin |
| GET | `/api/ops/monitoring` | admin |
| GET | `/api/ops/metrics` | admin |

## `/portfolios`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/portfolios` | admin |
| GET | `/api/portfolios` | viewer |
| GET | `/api/portfolios/{portfolio_id}` | viewer |
| DELETE | `/api/portfolios/{portfolio_id}` | admin |
| POST | `/api/portfolios/{portfolio_id}/snapshot` | admin |
| GET | `/api/portfolios/{portfolio_id}/snapshots` | viewer |

## `/performance`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/performance/record` | analyst |
| GET | `/api/performance` | viewer |
| GET | `/api/performance/history` | viewer |

## `/forecasts`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/forecasts/run` | analyst |
| GET | `/api/forecasts` | viewer |
| GET | `/api/forecasts/ledger/active` | viewer |
| GET | `/api/forecasts/{forecast_id}` | viewer |
| POST | `/api/forecasts/{forecast_id}/supersede` | admin |

## `/evaluation`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/evaluation/run` | analyst |
| GET | `/api/evaluation/scores` | viewer |
| GET | `/api/evaluation/summary` | viewer |

## `/tournaments`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/tournaments/run` | analyst |
| GET | `/api/tournaments` | viewer |
| GET | `/api/tournaments/{tournament_id}` | viewer |

## `/scenarios`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/scenarios/run` | analyst |
| GET | `/api/scenarios` | viewer |

## `/self-eval`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/self-eval/run` | analyst |
| GET | `/api/self-eval/latest` | viewer |
| GET | `/api/self-eval/history` | viewer |

## `/settings`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| GET | `/api/settings/providers` | admin |
| GET | `/api/settings/providers/catalog` | admin |
| POST | `/api/settings/providers` | admin |
| PUT | `/api/settings/providers/{provider_id}` | admin |
| POST | `/api/settings/providers/{provider_id}/key` | admin |
| DELETE | `/api/settings/providers/{provider_id}` | admin |
| POST | `/api/settings/providers/{provider_id}/test` | admin |
| GET | `/api/settings/providers/{provider_id}/models` | admin |
| GET | `/api/settings/models` | admin |
| POST | `/api/settings/models` | admin |
| PUT | `/api/settings/models/{model_id}` | admin |
| POST | `/api/settings/models/{model_id}/verify` | admin |
| POST | `/api/settings/models/{model_id}/block` | admin |
| DELETE | `/api/settings/models/{model_id}` | admin |
| GET | `/api/settings/agent-assignments` | admin |
| PUT | `/api/settings/agent-assignments` | admin |
| GET | `/api/settings/diversity` | admin |
| GET | `/api/settings/app` | admin |
| PUT | `/api/settings/app` | admin |
| POST | `/api/settings/import-from-env` | admin |
| POST | `/api/settings/debate-runs/{run_id}/void` | admin |
| POST | `/api/settings/forecasts/{forecast_id}/void` | admin |
| GET | `/api/settings/spend-today` | admin |

## `/dispatch`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| GET | `/api/dispatch/status` | viewer |
| GET | `/api/dispatch/jobs` | viewer |
| POST | `/api/dispatch/{dispatch_id}/retry` | admin |
| POST | `/api/dispatch/{dispatch_id}/recover` | admin |
| POST | `/api/dispatch/run` | analyst |
| GET | `/api/dispatch/articles/{article_id}` | viewer |

## `/local-runtimes`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| GET | `/api/local-runtimes/status` | admin |
| GET | `/api/local-runtimes/status/{name}` | admin |
| PUT | `/api/local-runtimes/status/{name}/enabled` | admin |
| POST | `/api/local-runtimes/status/{name}/start` | admin |
| POST | `/api/local-runtimes/status/{name}/stop` | admin |

## `/screening`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/screening/screen` | analyst |
| GET | `/api/screening/queue` | viewer |
| POST | `/api/screening/review/{article_id}/ack` | analyst |

## `/research`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/research/graphrag` | analyst |
| GET | `/api/research/methods` | viewer |

## `/risk`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/risk/analyze` | analyst |
| GET | `/api/risk/assessments` | viewer |
| GET | `/api/risk/overview` | viewer |

## `/decisions`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/decisions/run` | analyst |
| POST | `/api/decisions/from-debate` | analyst |
| GET | `/api/decisions` | viewer |
| GET | `/api/decisions/{decision_id}` | viewer |

## `/learning`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| POST | `/api/learning/run` | analyst |
| GET | `/api/learning/insights` | viewer |

## `/iran`

| متد | مسیر | حداقل نقش |
| --- | --- | --- |
| GET | `/api/iran/brief` | viewer |
| GET | `/api/iran/events` | viewer |
| POST | `/api/iran/transmission/analyze` | analyst |
| GET | `/api/iran/transmission` | viewer |

## استثناها و دلیلشان

- `POST /api/screening/review/{article_id}/ack` → `analyst` (تأیید کار صف بررسی، نه تغییر پیکربندی).
- `POST /api/alerts/evaluate` → `analyst` (اجرای قواعد موجود؛ ساختن/تغییر قاعده `admin` است).
- `POST /api/briefings/daily|weekly`، `POST /api/audit/replay`، `POST /api/dispatch/run` → `analyst`
  (تولید خروجی تحلیلی، بدون تغییر تنظیمات یا اعتبارنامه).
- `POST /api/ai/chat|generate` → `analyst` (هزینه‌ی مدل مصرف می‌شود، پس viewer نه).
- `POST /api/audit/log` → `analyst` (ثبت رویداد audit توسط خود کاربر؛ `actor` از نشست گرفته
  می‌شود و این مسیر تنظیمات یا اعتبارنامه را تغییر نمی‌دهد).
- `POST /api/sources/{id}/preview|health|recheck` → `admin` (وضعیت رجیستری منبع را تغییر می‌دهد).
- خواندن `/api/settings/*`, `/api/archive/*`, `/api/audit/*`, `/api/local-runtimes/*`, `/api/ops/*`
  → `admin` چون اعتبارنامه/مسیرهای عملیاتی را افشا می‌کنند، نه داده‌ی تحلیلی.
- `/api/dispatch/{id}/retry|recover` و `POST /api/jobs/trigger` → `admin` (عملیات زیرساختی).
- `POST /api/portfolios` و ویرایش‌های آن → `admin` (نوشتن؛ اگر بعداً «سبد شخصی» لازم شد،
  باید مالکیت ردیفی اضافه شود، نه نقش پایین‌تر).

## تضمین سازگاری

- `X-API-Key` معتبر (n8n، اسکریپت‌ها) → نقش `admin`، پس همه‌ی فراخوانی‌های فعلی دست‌نخورده‌اند.
- در `development` بدون `API_KEY` مسیر توسعه‌ای (dev bypass) مثل قبل نقش `admin` می‌دهد.
- ۴۰۱ (`AUTH_REQUIRED`/`INVALID_API_KEY`) پیش از بررسی نقش برمی‌گردد؛ ۴۰۳ برای کمبود نقش
  `error.details = {required, role, path, method}` دارد و UI از آن پیام فارسی می‌سازد.
